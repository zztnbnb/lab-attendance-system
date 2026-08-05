from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.entities import AttendanceSession, AttendanceStatus, User
from app.schemas.attendance import AttendancePublic, UserStatistics
from app.schemas.common import Page
from app.services.statistics import attendance_public, user_statistics


router = APIRouter(prefix="/me", tags=["个人中心"])


@router.get("/attendance-sessions", response_model=Page[AttendancePublic])
async def my_attendance(
    attendance_status: AttendanceStatus | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    filters = [AttendanceSession.user_id == user.id]
    if attendance_status:
        filters.append(AttendanceSession.status == attendance_status)
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


@router.get("/statistics", response_model=UserStatistics)
async def my_statistics(
    days: int = Query(30, ge=7, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await user_statistics(db, user.id, days)
