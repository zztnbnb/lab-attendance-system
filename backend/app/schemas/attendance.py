from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.entities import AttendanceStatus
from app.schemas.common import ORMModel


class AttendancePublic(ORMModel):
    id: UUID
    user_id: UUID
    check_in_at: datetime
    check_out_at: datetime | None
    duration_seconds: int | None
    status: AttendanceStatus
    corrected: bool
    correction_reason: str | None
    user_name: str | None = None
    username: str | None = None


class AttendanceCorrection(BaseModel):
    check_out_at: datetime
    reason: str = Field(min_length=2, max_length=500)


class AttendanceInvalidate(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class DailyDuration(BaseModel):
    date: date
    duration_seconds: int


class UserStatistics(BaseModel):
    today_seconds: int
    week_seconds: int
    month_seconds: int
    ongoing_since: datetime | None
    ongoing_seconds: int
    daily: list[DailyDuration]
    recent_sessions: list[AttendancePublic]


class RankingItem(BaseModel):
    user_id: UUID
    real_name: str
    username: str
    duration_seconds: int
    checkin_count: int = 0
    checkout_count: int = 0
    is_active: bool = True


class HourlyCount(BaseModel):
    hour: int
    count: int


class CurrentUserItem(BaseModel):
    user_id: UUID
    real_name: str
    username: str
    check_in_at: datetime


class AdminStatistics(BaseModel):
    current_count: int
    current_users: list[CurrentUserItem]
    today_checkins: int
    today_checkouts: int
    exception_count: int
    daily: list[DailyDuration]
    ranking: list[RankingItem]
    hourly: list[HourlyCount]
