from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import utcnow
from app.models.entities import AttendanceSession, AttendanceStatus, User
from app.schemas.attendance import (
    AdminStatistics,
    AttendancePublic,
    CurrentUserItem,
    DailyDuration,
    HourlyCount,
    RankingItem,
    UserStatistics,
)


LOCAL_TZ = ZoneInfo(settings.timezone)


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=LOCAL_TZ)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def split_duration_by_local_day(start: datetime, end: datetime) -> dict[date, int]:
    if end <= start:
        return {}
    start_local = start.astimezone(LOCAL_TZ)
    end_local = end.astimezone(LOCAL_TZ)
    cursor = start_local
    result: dict[date, int] = defaultdict(int)
    while cursor < end_local:
        next_midnight = datetime.combine(cursor.date() + timedelta(days=1), time.min, tzinfo=LOCAL_TZ)
        segment_end = min(end_local, next_midnight)
        result[cursor.date()] += max(0, int((segment_end - cursor).total_seconds()))
        cursor = segment_end
    return dict(result)


def attendance_public(session: AttendanceSession) -> AttendancePublic:
    item = AttendancePublic.model_validate(session)
    if session.user:
        item.user_name = session.user.real_name
        item.username = session.user.username
    return item


async def user_statistics(db: AsyncSession, user_id: UUID, days: int = 30) -> UserStatistics:
    now = utcnow()
    local_today = now.astimezone(LOCAL_TZ).date()
    range_start, _ = local_day_bounds(local_today - timedelta(days=max(days - 1, 30)))
    sessions = (
        await db.execute(
            select(AttendanceSession)
            .where(
                AttendanceSession.user_id == user_id,
                AttendanceSession.check_in_at >= range_start,
            )
            .order_by(AttendanceSession.check_in_at.desc())
            .options(selectinload(AttendanceSession.user))
        )
    ).scalars().all()

    totals: dict[date, int] = defaultdict(int)
    ongoing_since = None
    for session in sessions:
        if session.status == AttendanceStatus.OPEN:
            ongoing_since = session.check_in_at
        if session.status == AttendanceStatus.CLOSED and session.check_out_at:
            for day, seconds in split_duration_by_local_day(session.check_in_at, session.check_out_at).items():
                totals[day] += seconds

    week_start = local_today - timedelta(days=local_today.weekday())
    month_start = local_today.replace(day=1)
    daily = [
        DailyDuration(date=day, duration_seconds=totals.get(day, 0))
        for day in (local_today - timedelta(days=offset) for offset in reversed(range(days)))
    ]
    return UserStatistics(
        today_seconds=totals.get(local_today, 0),
        week_seconds=sum(value for day, value in totals.items() if week_start <= day <= local_today),
        month_seconds=sum(value for day, value in totals.items() if month_start <= day <= local_today),
        ongoing_since=ongoing_since,
        ongoing_seconds=max(0, int((now - ongoing_since).total_seconds())) if ongoing_since else 0,
        daily=daily,
        recent_sessions=[attendance_public(item) for item in sessions[:20]],
    )


async def admin_statistics(db: AsyncSession, days: int = 14) -> AdminStatistics:
    now = utcnow()
    local_today = now.astimezone(LOCAL_TZ).date()
    range_start, _ = local_day_bounds(local_today - timedelta(days=days - 1))
    _, range_end = local_day_bounds(local_today)
    today_start, today_end = local_day_bounds(local_today)

    sessions = (
        await db.execute(
            select(AttendanceSession)
            .where(AttendanceSession.check_in_at < range_end)
            .where(
                (AttendanceSession.check_out_at.is_(None)) | (AttendanceSession.check_out_at >= range_start)
            )
            .options(selectinload(AttendanceSession.user))
        )
    ).scalars().all()

    totals: dict[date, int] = defaultdict(int)
    user_totals: dict[UUID, int] = defaultdict(int)
    user_checkins: dict[UUID, int] = defaultdict(int)
    user_checkouts: dict[UUID, int] = defaultdict(int)
    hourly = Counter()
    current = []
    today_checkins = 0
    today_checkouts = 0
    exceptions = 0
    users: dict[UUID, User] = {}
    all_users = (await db.execute(select(User).order_by(User.real_name))).scalars().all()
    users.update({user.id: user for user in all_users})

    for session in sessions:
        users[session.user_id] = session.user
        user_checkins[session.user_id] += 1
        if session.status == AttendanceStatus.OPEN:
            current.append(
                CurrentUserItem(
                    user_id=session.user_id,
                    real_name=session.user.real_name,
                    username=session.user.username,
                    check_in_at=session.check_in_at,
                )
            )
        if session.status == AttendanceStatus.MISSING_CHECKOUT:
            exceptions += 1
        if today_start <= session.check_in_at < today_end:
            today_checkins += 1
            hourly[session.check_in_at.astimezone(LOCAL_TZ).hour] += 1
        if session.check_out_at and today_start <= session.check_out_at < today_end:
            today_checkouts += 1
        if session.check_out_at:
            user_checkouts[session.user_id] += 1
        if session.status == AttendanceStatus.CLOSED and session.check_out_at:
            for day, seconds in split_duration_by_local_day(session.check_in_at, session.check_out_at).items():
                if range_start.date() <= day <= local_today:
                    totals[day] += seconds
                    user_totals[session.user_id] += seconds

    ranking = sorted(users.items(), key=lambda item: (-user_totals.get(item[0], 0), item[1].real_name))
    return AdminStatistics(
        current_count=len(current),
        current_users=sorted(current, key=lambda item: item.check_in_at),
        today_checkins=today_checkins,
        today_checkouts=today_checkouts,
        exception_count=exceptions,
        daily=[
            DailyDuration(date=day, duration_seconds=totals.get(day, 0))
            for day in (local_today - timedelta(days=offset) for offset in reversed(range(days)))
        ],
        ranking=[
            RankingItem(
                user_id=user_id,
                real_name=users[user_id].real_name,
                username=users[user_id].username,
                duration_seconds=user_totals.get(user_id, 0),
                checkin_count=user_checkins.get(user_id, 0),
                checkout_count=user_checkouts.get(user_id, 0),
                is_active=users[user_id].is_active,
            )
            for user_id, _user in ranking
        ],
        hourly=[HourlyCount(hour=hour, count=hourly.get(hour, 0)) for hour in range(24)],
    )
