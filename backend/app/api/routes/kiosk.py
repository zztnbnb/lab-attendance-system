from __future__ import annotations

import secrets
from datetime import timedelta
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_device, get_face_engine
from app.api.routes.face import read_and_process_frames
from app.core.security import create_recognition_ticket, decode_recognition_ticket, utcnow
from app.db.session import get_db
from app.models.entities import (
    AllowedAction,
    AttendanceSession,
    AttendanceStatus,
    ChallengeType,
    KioskDevice,
    RecognitionAttempt,
    RecognitionResult,
    RecognitionSession,
    RecognitionStatus,
)
from app.schemas.attendance import AttendancePublic, CurrentUserItem
from app.schemas.kiosk import (
    AttendanceActionRequest,
    DevicePublic,
    FaceBox,
    KioskDashboard,
    KioskPresencePage,
    KioskRecordItem,
    KioskRecordPage,
    RecognitionSessionPublic,
    RecognitionVerifyResponse,
)
from app.services.attendance import AttendanceRuleError, consume_recognition_and_record, determine_allowed_action
from app.services.face_cache import face_cache
from app.services.face_engine import BaseFaceEngine, FaceFrame, evaluate_liveness
from app.services.statistics import LOCAL_TZ, local_day_bounds


router = APIRouter(prefix="/kiosk", tags=["打卡终端"])


PROMPTS = {
    ChallengeType.STATIC: "请正对摄像头并保持不动",
    ChallengeType.TURN_LEFT: "请缓慢向左转头，再回到正面",
    ChallengeType.TURN_RIGHT: "请缓慢向右转头，再回到正面",
}


def _face_box(frames: list[FaceFrame]) -> FaceBox | None:
    with_box = [frame for frame in frames if frame.face_box]
    if not with_box:
        return None
    x, y, width, height = max(with_box, key=lambda item: item.quality).face_box  # type: ignore[misc]
    return FaceBox(x=x, y=y, width=width, height=height)


def _quality_hint(frames: list[FaceFrame]) -> str | None:
    if not frames:
        return None
    quality = sum(frame.quality for frame in frames) / len(frames)
    return f"{len(frames)} 帧有效画面，平均质量 {round(quality * 100)}%"


def _verify_response(
    started_at: float,
    frames: list[FaceFrame],
    **kwargs: object,
) -> RecognitionVerifyResponse:
    return RecognitionVerifyResponse(
        **kwargs,
        face_box=_face_box(frames),
        quality_hint=_quality_hint(frames),
        processing_ms=max(1, round((perf_counter() - started_at) * 1000)),
        processed_at=utcnow(),
    )


async def _today_record_items(db: AsyncSession) -> list[KioskRecordItem]:
    local_today = utcnow().astimezone(LOCAL_TZ).date()
    start, end = local_day_bounds(local_today)
    sessions = (
        await db.execute(
            select(AttendanceSession)
            .where(
                or_(
                    and_(AttendanceSession.check_in_at >= start, AttendanceSession.check_in_at < end),
                    and_(AttendanceSession.check_out_at >= start, AttendanceSession.check_out_at < end),
                )
            )
            .options(selectinload(AttendanceSession.user))
        )
    ).scalars().all()
    attempts = (
        await db.execute(
            select(RecognitionAttempt).where(
                RecognitionAttempt.created_at >= start,
                RecognitionAttempt.created_at < end,
                RecognitionAttempt.result != RecognitionResult.MATCHED,
            )
        )
    ).scalars().all()

    records: list[KioskRecordItem] = []
    for attendance in sessions:
        if start <= attendance.check_in_at < end:
            records.append(
                KioskRecordItem(
                    id=f"{attendance.id}:in",
                    real_name=attendance.user.real_name,
                    action=AllowedAction.CHECK_IN,
                    result="SUCCESS",
                    occurred_at=attendance.check_in_at,
                )
            )
        if attendance.check_out_at and start <= attendance.check_out_at < end:
            records.append(
                KioskRecordItem(
                    id=f"{attendance.id}:out",
                    real_name=attendance.user.real_name,
                    action=AllowedAction.CHECK_OUT,
                    result="SUCCESS",
                    occurred_at=attendance.check_out_at,
                )
            )
    for attempt in attempts:
        records.append(
            KioskRecordItem(
                id=f"{attempt.id}:attempt",
                result=attempt.result.value,
                occurred_at=attempt.created_at,
            )
        )
    return sorted(records, key=lambda item: item.occurred_at, reverse=True)


@router.get("/device", response_model=DevicePublic)
async def device_status(device: KioskDevice = Depends(get_device)):
    return device


@router.get("/dashboard", response_model=KioskDashboard)
async def kiosk_dashboard(
    request: Request,
    device: KioskDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    now = utcnow()
    start, end = local_day_bounds(now.astimezone(LOCAL_TZ).date())
    current_count = await db.scalar(
        select(func.count()).select_from(AttendanceSession).where(AttendanceSession.status == AttendanceStatus.OPEN)
    )
    today_checkins = await db.scalar(
        select(func.count())
        .select_from(AttendanceSession)
        .where(AttendanceSession.check_in_at >= start, AttendanceSession.check_in_at < end)
    )
    today_checkouts = await db.scalar(
        select(func.count())
        .select_from(AttendanceSession)
        .where(AttendanceSession.check_out_at >= start, AttendanceSession.check_out_at < end)
    )
    exception_count = await db.scalar(
        select(func.count())
        .select_from(AttendanceSession)
        .where(AttendanceSession.status == AttendanceStatus.MISSING_CHECKOUT)
    )
    engine = getattr(request.app.state, "face_engine", None)
    return KioskDashboard(
        device=DevicePublic.model_validate(device),
        engine_status=getattr(request.app.state, "face_engine_status", "unknown"),
        engine_version=getattr(engine, "model_version", None),
        server_time=now,
        current_count=current_count or 0,
        today_checkins=today_checkins or 0,
        today_checkouts=today_checkouts or 0,
        exception_count=exception_count or 0,
        recent_records=(await _today_record_items(db))[:5],
    )


@router.get("/presence", response_model=KioskPresencePage)
async def kiosk_presence(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: KioskDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    filters = [AttendanceSession.status == AttendanceStatus.OPEN]
    total = await db.scalar(select(func.count()).select_from(AttendanceSession).where(*filters))
    sessions = (
        await db.execute(
            select(AttendanceSession)
            .where(*filters)
            .order_by(AttendanceSession.check_in_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(AttendanceSession.user))
        )
    ).scalars().all()
    return KioskPresencePage(
        items=[
            CurrentUserItem(
                user_id=item.user_id,
                real_name=item.user.real_name,
                username=item.user.username,
                check_in_at=item.check_in_at,
            )
            for item in sessions
        ],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/records", response_model=KioskRecordPage)
async def kiosk_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: KioskDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    records = await _today_record_items(db)
    start = (page - 1) * page_size
    return KioskRecordPage(
        items=records[start : start + page_size],
        total=len(records),
        page=page,
        page_size=page_size,
    )


@router.post("/recognition-sessions", response_model=RecognitionSessionPublic, status_code=status.HTTP_201_CREATED)
async def create_recognition_session(
    device: KioskDevice = Depends(get_device), db: AsyncSession = Depends(get_db)
):
    challenge = ChallengeType.STATIC
    session = RecognitionSession(
        device_id=device.id,
        challenge=challenge,
        nonce=secrets.token_urlsafe(24),
        expires_at=utcnow() + timedelta(seconds=60),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return RecognitionSessionPublic(
        id=session.id,
        challenge=challenge,
        prompt=PROMPTS[challenge],
        expires_at=session.expires_at,
    )


@router.post("/recognition-sessions/{session_id}/verify", response_model=RecognitionVerifyResponse)
async def verify_recognition_session(
    session_id: UUID,
    files: list[UploadFile] = File(...),
    device: KioskDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
    engine: BaseFaceEngine = Depends(get_face_engine),
):
    started_at = perf_counter()
    recognition = (
        await db.execute(
            select(RecognitionSession)
            .where(RecognitionSession.id == session_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    now = utcnow()
    if recognition is None or recognition.device_id != device.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "识别会话不存在")
    if recognition.status != RecognitionStatus.CREATED or recognition.expires_at <= now:
        raise HTTPException(status.HTTP_410_GONE, "识别会话已过期或已使用")

    frames, messages = await read_and_process_frames(files, engine)
    if len(frames) < 3:
        recognition.status = RecognitionStatus.FAILED
        db.add(
            RecognitionAttempt(
                recognition_session_id=recognition.id,
                device_id=device.id,
                result=RecognitionResult.QUALITY_FAILED,
                model_version=engine.model_version,
            )
        )
        await db.commit()
        return _verify_response(
            started_at,
            frames,
            recognized=False,
            message="有效画面不足：" + "；".join(messages[:2]),
        )

    liveness = evaluate_liveness(frames, recognition.challenge)
    recognition.liveness_score = liveness.score
    if not liveness.passed:
        recognition.status = RecognitionStatus.FAILED
        db.add(
            RecognitionAttempt(
                recognition_session_id=recognition.id,
                device_id=device.id,
                result=RecognitionResult.LIVENESS_FAILED,
                liveness_score=liveness.score,
                model_version=engine.model_version,
            )
        )
        await db.commit()
        return _verify_response(
            started_at,
            frames,
            recognized=False,
            message=liveness.message,
            liveness_score=liveness.score,
        )

    match = await face_cache.match(frames)
    recognition.match_score = match.score
    recognition.second_score = match.second_score
    if match.identity is None:
        recognition.status = RecognitionStatus.FAILED
        db.add(
            RecognitionAttempt(
                recognition_session_id=recognition.id,
                device_id=device.id,
                result=RecognitionResult.UNKNOWN,
                match_score=match.score,
                liveness_score=liveness.score,
                model_version=engine.model_version,
            )
        )
        await db.commit()
        return _verify_response(
            started_at,
            frames,
            recognized=False,
            message="未找到匹配的人脸档案",
            match_score=match.score,
            liveness_score=liveness.score,
        )

    allowed_action, message = await determine_allowed_action(db, match.identity.user_id)
    recognition.status = RecognitionStatus.VERIFIED
    recognition.matched_user_id = match.identity.user_id
    recognition.allowed_action = allowed_action
    db.add(
        RecognitionAttempt(
            recognition_session_id=recognition.id,
            device_id=device.id,
            user_id=match.identity.user_id,
            result=RecognitionResult.MATCHED,
            match_score=match.score,
            liveness_score=liveness.score,
            model_version=engine.model_version,
        )
    )
    await db.commit()
    ticket = None
    if allowed_action != AllowedAction.BLOCKED:
        ticket = create_recognition_ticket(recognition.id, device.id, allowed_action.value)
    return _verify_response(
        started_at,
        frames,
        recognized=True,
        user_id=match.identity.user_id,
        real_name=match.identity.real_name,
        allowed_action=allowed_action,
        message=message,
        ticket=ticket,
        match_score=match.score,
        liveness_score=liveness.score,
    )


@router.post("/attendance-actions", response_model=AttendancePublic)
async def attendance_action(
    payload: AttendanceActionRequest,
    device: KioskDevice = Depends(get_device),
    db: AsyncSession = Depends(get_db),
):
    try:
        ticket = decode_recognition_ticket(payload.ticket)
        recognition_id = UUID(ticket["sub"])
        ticket_device = UUID(ticket["device"])
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "识别凭证无效或已过期") from exc
    if ticket_device != device.id or ticket.get("action") != payload.action.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "识别凭证与终端或操作不匹配")
    try:
        attendance = await consume_recognition_and_record(
            db,
            recognition_id=recognition_id,
            device_id=device.id,
            action=payload.action,
            idempotency_key=payload.idempotency_key,
        )
    except AttendanceRuleError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return AttendancePublic.model_validate(attendance)
