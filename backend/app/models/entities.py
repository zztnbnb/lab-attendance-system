from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.base import Base
from app.db.types import UTCDateTime


class Role(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class FaceProfileStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    REPLACED = "REPLACED"
    REVOKED = "REVOKED"


class EnrollmentMode(str, enum.Enum):
    SELF = "SELF"
    ADMIN = "ADMIN"


class EnrollmentStatus(str, enum.Enum):
    COLLECTING = "COLLECTING"
    SUBMITTED = "SUBMITTED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"


class AttendanceStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    MISSING_CHECKOUT = "MISSING_CHECKOUT"
    INVALID = "INVALID"


class AllowedAction(str, enum.Enum):
    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"
    BLOCKED = "BLOCKED"


class RecognitionStatus(str, enum.Enum):
    CREATED = "CREATED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


class RecognitionResult(str, enum.Enum):
    MATCHED = "MATCHED"
    UNKNOWN = "UNKNOWN"
    LIVENESS_FAILED = "LIVENESS_FAILED"
    QUALITY_FAILED = "QUALITY_FAILED"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    ERROR = "ERROR"


class ChallengeType(str, enum.Enum):
    STATIC = "STATIC"
    TURN_LEFT = "TURN_LEFT"
    TURN_RIGHT = "TURN_RIGHT"


enum_kwargs = {"native_enum": False, "validate_strings": True}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    real_name: Mapped[str] = mapped_column(String(100), nullable=False)
    identifier: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, **enum_kwargs), default=Role.USER, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    face_profiles: Mapped[list[FaceProfile]] = relationship(
        back_populates="user", foreign_keys="FaceProfile.user_id", cascade="all, delete-orphan"
    )
    attendance_sessions: Mapped[list[AttendanceSession]] = relationship(
        back_populates="user", foreign_keys="AttendanceSession.user_id", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    user: Mapped[User] = relationship()


class FaceProfile(Base):
    __tablename__ = "face_profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[FaceProfileStatus] = mapped_column(
        Enum(FaceProfileStatus, **enum_kwargs), default=FaceProfileStatus.DRAFT, index=True
    )
    mode: Mapped[EnrollmentMode] = mapped_column(Enum(EnrollmentMode, **enum_kwargs), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    submitted_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    live_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship(back_populates="face_profiles", foreign_keys=[user_id])
    submitted_by: Mapped[User] = relationship(foreign_keys=[submitted_by_id])
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id])
    templates: Mapped[list[FaceTemplate]] = relationship(back_populates="profile", cascade="all, delete-orphan")

    __table_args__ = (
        Index(
            "uq_face_profile_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )


class FaceTemplate(Base):
    __tablename__ = "face_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("face_profiles.id", ondelete="CASCADE"), index=True)
    pose: Mapped[str] = mapped_column(String(32), default="FRONT", nullable=False)
    encrypted_embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary(12), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    profile: Mapped[FaceProfile] = relationship(back_populates="templates")


class EnrollmentSession(Base):
    __tablename__ = "enrollment_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("face_profiles.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus, **enum_kwargs), default=EnrollmentStatus.COLLECTING, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    profile: Mapped[FaceProfile] = relationship()


class KioskDevice(TimestampMixin, Base):
    __tablename__ = "kiosk_devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    credential_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class RecognitionSession(Base):
    __tablename__ = "recognition_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kiosk_devices.id"), index=True)
    challenge: Mapped[ChallengeType] = mapped_column(Enum(ChallengeType, **enum_kwargs), nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[RecognitionStatus] = mapped_column(
        Enum(RecognitionStatus, **enum_kwargs), default=RecognitionStatus.CREATED, index=True
    )
    matched_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    second_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    allowed_action: Mapped[AllowedAction | None] = mapped_column(Enum(AllowedAction, **enum_kwargs), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attendance_session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attendance_sessions.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    device: Mapped[KioskDevice] = relationship()
    matched_user: Mapped[User | None] = relationship()
    attendance_session: Mapped[AttendanceSession | None] = relationship(foreign_keys=[attendance_session_id])


class AttendanceSession(TimestampMixin, Base):
    __tablename__ = "attendance_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    check_in_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True, nullable=False)
    check_out_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, **enum_kwargs), default=AttendanceStatus.OPEN, index=True
    )
    check_in_device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kiosk_devices.id"), nullable=False)
    check_out_device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("kiosk_devices.id"), nullable=True)
    check_in_score: Mapped[float] = mapped_column(Float, nullable=False)
    check_out_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    corrected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    correction_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    corrected_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    user: Mapped[User] = relationship(back_populates="attendance_sessions", foreign_keys=[user_id])
    corrected_by: Mapped[User | None] = relationship(foreign_keys=[corrected_by_id])

    __table_args__ = (
        Index(
            "uq_attendance_unfinished_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('OPEN', 'MISSING_CHECKOUT')"),
            sqlite_where=text("status IN ('OPEN', 'MISSING_CHECKOUT')"),
        ),
        Index("ix_attendance_user_time", "user_id", "check_in_at"),
    )


class RecognitionAttempt(Base):
    __tablename__ = "recognition_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recognition_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recognition_sessions.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("kiosk_devices.id"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    result: Mapped[RecognitionResult] = mapped_column(Enum(RecognitionResult, **enum_kwargs), index=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    actor_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kiosk_devices.id"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    before_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
