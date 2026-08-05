from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.entities import EnrollmentMode, EnrollmentStatus, FaceProfileStatus
from app.schemas.common import ORMModel


class EnrollmentCreate(BaseModel):
    target_user_id: UUID | None = None
    mode: EnrollmentMode = EnrollmentMode.SELF


class EnrollmentPublic(ORMModel):
    id: UUID
    profile_id: UUID
    user_id: UUID
    status: EnrollmentStatus
    expires_at: datetime
    created_at: datetime


class FrameProcessResponse(BaseModel):
    accepted: int
    rejected: int
    template_count: int
    average_quality: float
    liveness_score: float
    messages: list[str]


class FaceProfilePublic(ORMModel):
    id: UUID
    user_id: UUID
    status: FaceProfileStatus
    mode: EnrollmentMode
    model_version: str
    quality_score: float | None
    liveness_score: float | None
    live_verified_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    submitted_at: datetime | None
    reviewed_at: datetime | None
    template_count: int = 0
    user_name: str | None = None
    username: str | None = None


class RejectFaceRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class LiveVerifyResponse(BaseModel):
    verified: bool
    score: float
    threshold: float
