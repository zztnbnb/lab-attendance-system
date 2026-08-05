from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import utcnow
from app.models.entities import (
    AllowedAction,
    AttendanceSession,
    AttendanceStatus,
    RecognitionSession,
    RecognitionStatus,
)
from app.services.audit import add_audit


class AttendanceRuleError(RuntimeError):
    pass


async def get_unfinished_session(
    db: AsyncSession, user_id: UUID, *, for_update: bool = False
) -> AttendanceSession | None:
    query = select(AttendanceSession).where(
        AttendanceSession.user_id == user_id,
        AttendanceSession.status.in_([AttendanceStatus.OPEN, AttendanceStatus.MISSING_CHECKOUT]),
    )
    if for_update:
        query = query.with_for_update()
    return (await db.execute(query)).scalar_one_or_none()


async def determine_allowed_action(db: AsyncSession, user_id: UUID) -> tuple[AllowedAction, str]:
    unfinished = await get_unfinished_session(db, user_id)
    if unfinished is None:
        return AllowedAction.CHECK_IN, "识别成功，可以签到"
    if unfinished.status == AttendanceStatus.MISSING_CHECKOUT:
        return AllowedAction.BLOCKED, "存在漏签退异常，请联系管理员处理"
    return AllowedAction.CHECK_OUT, "识别成功，可以签退"


async def consume_recognition_and_record(
    db: AsyncSession,
    *,
    recognition_id: UUID,
    device_id: UUID,
    action: AllowedAction,
    idempotency_key: str,
    now: datetime | None = None,
) -> AttendanceSession:
    now = now or utcnow()
    recognition = (
        await db.execute(
            select(RecognitionSession)
            .where(RecognitionSession.id == recognition_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if recognition is None or recognition.device_id != device_id:
        raise AttendanceRuleError("识别凭证无效")
    if recognition.status == RecognitionStatus.CONSUMED:
        if recognition.idempotency_key == idempotency_key and recognition.attendance_session_id:
            existing = await db.get(AttendanceSession, recognition.attendance_session_id)
            if existing:
                return existing
        raise AttendanceRuleError("识别凭证已使用")
    if recognition.status != RecognitionStatus.VERIFIED or recognition.expires_at <= now:
        raise AttendanceRuleError("识别凭证已失效")
    if recognition.allowed_action != action or action == AllowedAction.BLOCKED:
        raise AttendanceRuleError("当前状态不允许该操作")
    if recognition.matched_user_id is None or recognition.match_score is None:
        raise AttendanceRuleError("识别凭证缺少用户信息")

    unfinished = await get_unfinished_session(db, recognition.matched_user_id, for_update=True)
    if action == AllowedAction.CHECK_IN:
        if unfinished is not None:
            raise AttendanceRuleError("已经签到，不能重复签到")
        attendance = AttendanceSession(
            user_id=recognition.matched_user_id,
            check_in_at=now,
            status=AttendanceStatus.OPEN,
            check_in_device_id=device_id,
            check_in_score=recognition.match_score,
        )
        db.add(attendance)
        await db.flush()
        add_audit(
            db,
            action="ATTENDANCE_CHECK_IN",
            target_type="attendance_session",
            target_id=attendance.id,
            actor_device_id=device_id,
            after={"status": AttendanceStatus.OPEN.value, "user_id": str(attendance.user_id)},
        )
    else:
        if unfinished is None:
            raise AttendanceRuleError("尚未签到，不能签退")
        if unfinished.status == AttendanceStatus.MISSING_CHECKOUT:
            raise AttendanceRuleError("漏签退异常必须由管理员处理")
        unfinished.check_out_at = now
        unfinished.duration_seconds = max(0, int((now - unfinished.check_in_at).total_seconds()))
        unfinished.status = AttendanceStatus.CLOSED
        unfinished.check_out_device_id = device_id
        unfinished.check_out_score = recognition.match_score
        attendance = unfinished
        add_audit(
            db,
            action="ATTENDANCE_CHECK_OUT",
            target_type="attendance_session",
            target_id=attendance.id,
            actor_device_id=device_id,
            after={"status": AttendanceStatus.CLOSED.value, "duration_seconds": attendance.duration_seconds},
        )

    recognition.status = RecognitionStatus.CONSUMED
    recognition.consumed_at = now
    recognition.idempotency_key = idempotency_key
    recognition.attendance_session_id = attendance.id
    await db.commit()
    await db.refresh(attendance)
    return attendance
