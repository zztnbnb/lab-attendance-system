from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.entities import AllowedAction, ChallengeType
from app.schemas.attendance import CurrentUserItem
from app.schemas.common import Page


class RecognitionSessionPublic(BaseModel):
    id: UUID
    challenge: ChallengeType
    prompt: str
    expires_at: datetime


class FaceBox(BaseModel):
    """Face bounds normalized to the submitted frame dimensions."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class RecognitionVerifyResponse(BaseModel):
    recognized: bool
    user_id: UUID | None = None
    real_name: str | None = None
    allowed_action: AllowedAction = AllowedAction.BLOCKED
    message: str
    ticket: str | None = None
    match_score: float | None = None
    liveness_score: float | None = None
    face_box: FaceBox | None = None
    quality_hint: str | None = None
    processing_ms: int | None = None
    processed_at: datetime | None = None


class AttendanceActionRequest(BaseModel):
    ticket: str
    action: AllowedAction
    idempotency_key: str = Field(min_length=8, max_length=64)


class DeviceCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9-]+$", min_length=3, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=200)


class LocalDeviceBootstrap(BaseModel):
    installation_id: UUID
    name: str = Field(default="本机打卡终端", min_length=1, max_length=100)
    location: str = Field(default="当前电脑", min_length=1, max_length=200)


class DevicePublic(BaseModel):
    id: UUID
    code: str
    name: str
    location: str
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceCreated(DevicePublic):
    secret: str


class KioskRecordItem(BaseModel):
    id: str
    real_name: str | None = None
    action: AllowedAction | None = None
    result: str
    occurred_at: datetime


class KioskDashboard(BaseModel):
    device: DevicePublic
    engine_status: str
    engine_version: str | None = None
    server_time: datetime
    current_count: int
    today_checkins: int
    today_checkouts: int
    exception_count: int
    recent_records: list[KioskRecordItem]


class KioskRecordPage(Page[KioskRecordItem]):
    pass


class KioskPresencePage(Page[CurrentUserItem]):
    pass


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None
