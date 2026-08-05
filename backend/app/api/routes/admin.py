from __future__ import annotations

import csv
import io
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_admin
from app.core.security import hash_device_secret, new_device_secret, utcnow
from app.db.session import get_db
from app.models.entities import (
    AttendanceSession,
    AttendanceStatus,
    AuditLog,
    KioskDevice,
    User,
)
from app.schemas.attendance import (
    AdminStatistics,
    AttendanceCorrection,
    AttendanceInvalidate,
    AttendancePublic,
)
from app.schemas.audit import AuditLogPublic
from app.schemas.common import Message, Page
from app.schemas.kiosk import DeviceCreate, DeviceCreated, DevicePublic, DeviceUpdate, LocalDeviceBootstrap
from app.services.audit import add_audit
from app.services.statistics import LOCAL_TZ, admin_statistics, attendance_public


router = APIRouter(prefix="/admin", tags=["管理员"])


@router.get("/statistics", response_model=AdminStatistics)
async def statistics(
    days: int = Query(14, ge=7, le=90),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await admin_statistics(db, days)


@router.get("/attendance-sessions", response_model=Page[AttendancePublic])
async def list_attendance(
    user_id: UUID | None = None,
    attendance_status: AttendanceStatus | None = Query(default=None, alias="status"),
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if user_id:
        filters.append(AttendanceSession.user_id == user_id)
    if attendance_status:
        filters.append(AttendanceSession.status == attendance_status)
    if start_at:
        filters.append(AttendanceSession.check_in_at >= start_at)
    if end_at:
        filters.append(AttendanceSession.check_in_at < end_at)
    total = await db.scalar(select(func.count()).select_from(AttendanceSession).where(*filters))
    sessions = (
        await db.execute(
            select(AttendanceSession)
            .where(*filters)
            .order_by(AttendanceSession.check_in_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(AttendanceSession.user))
        )
    ).scalars().all()
    return Page(items=[attendance_public(item) for item in sessions], total=total or 0, page=page, page_size=page_size)


@router.post("/attendance-sessions/{session_id}/correct", response_model=AttendancePublic)
async def correct_attendance(
    session_id: UUID,
    payload: AttendanceCorrection,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    attendance = (
        await db.execute(
            select(AttendanceSession)
            .where(AttendanceSession.id == session_id)
            .with_for_update()
            .options(selectinload(AttendanceSession.user))
        )
    ).scalar_one_or_none()
    if attendance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "考勤记录不存在")
    if attendance.status == AttendanceStatus.INVALID:
        raise HTTPException(status.HTTP_409_CONFLICT, "无效记录不能补签退")
    if payload.check_out_at <= attendance.check_in_at:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "签退时间必须晚于签到时间")
    before = {
        "status": attendance.status.value,
        "check_out_at": attendance.check_out_at.isoformat() if attendance.check_out_at else None,
        "duration_seconds": attendance.duration_seconds,
    }
    attendance.check_out_at = payload.check_out_at
    attendance.duration_seconds = int((payload.check_out_at - attendance.check_in_at).total_seconds())
    attendance.status = AttendanceStatus.CLOSED
    attendance.corrected = True
    attendance.correction_reason = payload.reason
    attendance.corrected_by_id = admin.id
    add_audit(
        db,
        action="ATTENDANCE_CORRECTED",
        target_type="attendance_session",
        target_id=attendance.id,
        actor_user_id=admin.id,
        before=before,
        after={"status": AttendanceStatus.CLOSED.value, "check_out_at": payload.check_out_at.isoformat(), "duration_seconds": attendance.duration_seconds},
        reason=payload.reason,
    )
    await db.commit()
    return attendance_public(attendance)


@router.post("/attendance-sessions/{session_id}/invalidate", response_model=Message)
async def invalidate_attendance(
    session_id: UUID,
    payload: AttendanceInvalidate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    attendance = await db.get(AttendanceSession, session_id, with_for_update=True)
    if attendance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "考勤记录不存在")
    before = {"status": attendance.status.value, "duration_seconds": attendance.duration_seconds}
    attendance.status = AttendanceStatus.INVALID
    attendance.duration_seconds = None
    attendance.corrected = True
    attendance.correction_reason = payload.reason
    attendance.corrected_by_id = admin.id
    add_audit(
        db,
        action="ATTENDANCE_INVALIDATED",
        target_type="attendance_session",
        target_id=attendance.id,
        actor_user_id=admin.id,
        before=before,
        after={"status": AttendanceStatus.INVALID.value},
        reason=payload.reason,
    )
    await db.commit()
    return Message(message="考勤记录已标记为无效")


@router.get("/attendance-export.csv")
async def export_attendance(
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if start_at:
        filters.append(AttendanceSession.check_in_at >= start_at)
    if end_at:
        filters.append(AttendanceSession.check_in_at < end_at)
    sessions = (
        await db.execute(
            select(AttendanceSession)
            .where(*filters)
            .order_by(AttendanceSession.check_in_at.desc())
            .options(selectinload(AttendanceSession.user))
        )
    ).scalars().all()
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["用户名", "姓名", "签到时间", "签退时间", "时长（秒）", "状态", "是否修正"])
    for item in sessions:
        writer.writerow(
            [
                item.user.username,
                item.user.real_name,
                item.check_in_at.astimezone(LOCAL_TZ).isoformat(timespec="seconds"),
                item.check_out_at.astimezone(LOCAL_TZ).isoformat(timespec="seconds") if item.check_out_at else "",
                item.duration_seconds or "",
                item.status.value,
                "是" if item.corrected else "否",
            ]
        )
    data = output.getvalue().encode("utf-8")
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=attendance.csv"},
    )


@router.get("/devices", response_model=list[DevicePublic])
async def list_devices(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(KioskDevice).order_by(KioskDevice.created_at.desc()))).scalars().all()


@router.post("/devices", response_model=DeviceCreated, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    code = payload.code.upper()
    if await db.scalar(select(func.count()).select_from(KioskDevice).where(KioskDevice.code == code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "终端编号已存在")
    secret = new_device_secret()
    device = KioskDevice(
        code=code,
        name=payload.name,
        location=payload.location,
        credential_hash=hash_device_secret(secret),
        created_by_id=admin.id,
    )
    db.add(device)
    await db.flush()
    add_audit(db, action="DEVICE_CREATED", target_type="kiosk_device", target_id=device.id, actor_user_id=admin.id, after={"code": code, "location": payload.location})
    await db.commit()
    await db.refresh(device)
    return DeviceCreated(**DevicePublic.model_validate(device).model_dump(), secret=secret)


@router.post("/devices/bootstrap-local", response_model=DeviceCreated)
async def bootstrap_local_device(
    payload: LocalDeviceBootstrap,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create or repair the kiosk identity for the current browser installation."""
    installation_key = payload.installation_id.hex[:16].upper()
    code = f"LOCAL-{installation_key}"
    secret = new_device_secret()
    device = await db.scalar(select(KioskDevice).where(KioskDevice.code == code))

    if device is None:
        device = KioskDevice(
            code=code,
            name=payload.name,
            location=payload.location,
            credential_hash=hash_device_secret(secret),
            created_by_id=admin.id,
        )
        db.add(device)
        await db.flush()
        action = "DEVICE_LOCAL_BOOTSTRAPPED"
        before = None
    else:
        before = {"is_active": device.is_active, "credential_rotated": False}
        device.credential_hash = hash_device_secret(secret)
        device.is_active = True
        action = "DEVICE_LOCAL_REPAIRED"

    add_audit(
        db,
        action=action,
        target_type="kiosk_device",
        target_id=device.id,
        actor_user_id=admin.id,
        before=before,
        after={"code": code, "location": device.location, "is_active": True, "credential_rotated": True},
    )
    await db.commit()
    await db.refresh(device)
    return DeviceCreated(**DevicePublic.model_validate(device).model_dump(), secret=secret)


@router.patch("/devices/{device_id}", response_model=DevicePublic)
async def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    device = await db.get(KioskDevice, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "终端不存在")
    before = {"name": device.name, "location": device.location, "is_active": device.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    add_audit(db, action="DEVICE_UPDATED", target_type="kiosk_device", target_id=device.id, actor_user_id=admin.id, before=before, after={"name": device.name, "location": device.location, "is_active": device.is_active})
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/audit-logs", response_model=Page[AuditLogPublic])
async def list_audit_logs(
    action: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    filters = [AuditLog.action == action] if action else []
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*filters))
    logs = (
        await db.execute(
            select(AuditLog).where(*filters).order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return Page(items=logs, total=total or 0, page=page, page_size=page_size)
