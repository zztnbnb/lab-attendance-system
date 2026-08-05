from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, get_face_engine, require_admin
from app.core.config import settings
from app.core.security import EmbeddingCipher, utcnow
from app.db.session import get_db
from app.models.entities import (
    EnrollmentMode,
    EnrollmentSession,
    EnrollmentStatus,
    FaceProfile,
    FaceProfileStatus,
    FaceTemplate,
    Role,
    User,
)
from app.schemas.common import Message, Page
from app.schemas.face import (
    EnrollmentCreate,
    EnrollmentPublic,
    FaceProfilePublic,
    FrameProcessResponse,
    LiveVerifyResponse,
    RejectFaceRequest,
)
from app.services.audit import add_audit
from app.services.face_cache import face_cache
from app.services.face_engine import BaseFaceEngine, FaceEngineError, FaceFrame, evaluate_liveness


router = APIRouter(tags=["人脸档案"])
cipher = EmbeddingCipher()


def profile_public(profile: FaceProfile) -> FaceProfilePublic:
    item = FaceProfilePublic.model_validate(profile)
    item.template_count = len(profile.templates)
    if profile.user:
        item.user_name = profile.user.real_name
        item.username = profile.user.username
    return item


async def read_and_process_frames(files: list[UploadFile], engine: BaseFaceEngine) -> tuple[list[FaceFrame], list[str]]:
    if not files or len(files) > 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "每次需要上传 1–10 帧")
    frames: list[FaceFrame] = []
    messages: list[str] = []
    for index, upload in enumerate(files, start=1):
        if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            messages.append(f"第 {index} 帧格式不支持")
            continue
        content = await upload.read(settings.max_upload_bytes + 1)
        if len(content) > settings.max_upload_bytes:
            messages.append(f"第 {index} 帧超过大小限制")
            continue
        try:
            frame = await asyncio.to_thread(engine.process, content)
            frames.append(frame)
        except FaceEngineError as exc:
            messages.append(f"第 {index} 帧：{exc}")
    return frames, messages


async def load_enrollment(db: AsyncSession, enrollment_id: UUID) -> EnrollmentSession:
    enrollment = (
        await db.execute(
            select(EnrollmentSession)
            .where(EnrollmentSession.id == enrollment_id)
            .options(
                selectinload(EnrollmentSession.profile).selectinload(FaceProfile.templates),
                selectinload(EnrollmentSession.profile).selectinload(FaceProfile.user),
            )
        )
    ).scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "录入会话不存在")
    return enrollment


def ensure_enrollment_access(enrollment: EnrollmentSession, user: User) -> None:
    if user.role != Role.ADMIN and enrollment.created_by_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "无权访问该录入会话")
    if enrollment.status != EnrollmentStatus.COLLECTING:
        raise HTTPException(status.HTTP_409_CONFLICT, "录入会话已经结束")
    if enrollment.expires_at <= utcnow():
        raise HTTPException(status.HTTP_410_GONE, "录入会话已过期")


@router.post("/face/enrollment-sessions", response_model=EnrollmentPublic, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    payload: EnrollmentCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    engine: BaseFaceEngine = Depends(get_face_engine),
):
    target_id = payload.target_user_id or user.id
    mode = payload.mode
    if user.role != Role.ADMIN:
        if target_id != user.id or mode != EnrollmentMode.SELF:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "普通用户只能为自己提交人脸")
    elif payload.target_user_id and mode == EnrollmentMode.SELF:
        mode = EnrollmentMode.ADMIN
    target = await db.get(User, target_id)
    if target is None or not target.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "目标用户不存在或已停用")

    profile = FaceProfile(
        user_id=target.id,
        status=FaceProfileStatus.DRAFT,
        mode=mode,
        model_version=engine.model_version,
        submitted_by_id=user.id,
        key_version=settings.key_version,
    )
    db.add(profile)
    await db.flush()
    enrollment = EnrollmentSession(
        profile_id=profile.id,
        user_id=target.id,
        created_by_id=user.id,
        expires_at=utcnow() + timedelta(minutes=15),
    )
    db.add(enrollment)
    add_audit(
        db,
        action="FACE_ENROLLMENT_STARTED",
        target_type="face_profile",
        target_id=profile.id,
        actor_user_id=user.id,
        after={"user_id": str(target.id), "mode": mode.value},
    )
    await db.commit()
    await db.refresh(enrollment)
    return enrollment


@router.post("/face/enrollment-sessions/{enrollment_id}/frames", response_model=FrameProcessResponse)
async def add_enrollment_frames(
    enrollment_id: UUID,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    engine: BaseFaceEngine = Depends(get_face_engine),
):
    enrollment = await load_enrollment(db, enrollment_id)
    ensure_enrollment_access(enrollment, user)
    frames, messages = await read_and_process_frames(files, engine)
    if not frames:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"message": "没有可用的人脸帧", "errors": messages})
    liveness = evaluate_liveness(frames, None)
    if not liveness.passed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, liveness.message)

    existing = len(enrollment.profile.templates)
    accepted = 0
    for frame in frames[: max(0, 10 - existing)]:
        raw = frame.embedding.astype(np.float32).tobytes()
        encrypted, nonce = cipher.encrypt(raw, str(enrollment.profile.id).encode("ascii"))
        pose = "LEFT" if frame.yaw_proxy < -0.10 else "RIGHT" if frame.yaw_proxy > 0.10 else "FRONT"
        db.add(
            FaceTemplate(
                profile_id=enrollment.profile.id,
                pose=pose,
                encrypted_embedding=encrypted,
                nonce=nonce,
                dimension=frame.embedding.size,
                quality_score=frame.quality,
            )
        )
        accepted += 1
    all_qualities = [item.quality_score for item in enrollment.profile.templates] + [f.quality for f in frames[:accepted]]
    enrollment.profile.quality_score = sum(all_qualities) / len(all_qualities)
    enrollment.profile.liveness_score = liveness.score
    await db.commit()
    return FrameProcessResponse(
        accepted=accepted,
        rejected=len(files) - len(frames),
        template_count=existing + accepted,
        average_quality=enrollment.profile.quality_score,
        liveness_score=liveness.score,
        messages=messages,
    )


@router.post("/face/enrollment-sessions/{enrollment_id}/submit", response_model=FaceProfilePublic)
async def submit_enrollment(
    enrollment_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    enrollment = await load_enrollment(db, enrollment_id)
    ensure_enrollment_access(enrollment, user)
    profile = enrollment.profile
    if len(profile.templates) < settings.min_face_templates:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"至少需要 {settings.min_face_templates} 个有效模板")
    if (profile.liveness_score or 0) < 0.55:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "活体分数不足，请重新录入")
    now = utcnow()
    profile.submitted_at = now
    enrollment.status = EnrollmentStatus.SUBMITTED
    if profile.mode == EnrollmentMode.ADMIN:
        await db.execute(
            update(FaceProfile)
            .where(FaceProfile.user_id == profile.user_id, FaceProfile.status == FaceProfileStatus.ACTIVE)
            .values(status=FaceProfileStatus.REPLACED, reviewed_at=now)
        )
        profile.status = FaceProfileStatus.ACTIVE
        profile.approved_by_id = user.id
        profile.reviewed_at = now
        profile.live_verified_at = now
        enrollment.status = EnrollmentStatus.COMPLETED
        action = "FACE_PROFILE_ADMIN_ACTIVATED"
    else:
        profile.status = FaceProfileStatus.PENDING
        action = "FACE_PROFILE_SUBMITTED"
    add_audit(
        db,
        action=action,
        target_type="face_profile",
        target_id=profile.id,
        actor_user_id=user.id,
        after={"status": profile.status.value, "templates": len(profile.templates)},
    )
    await db.commit()
    if profile.status == FaceProfileStatus.ACTIVE:
        await face_cache.refresh(db)
    return profile_public(profile)


@router.get("/me/face-profile", response_model=list[FaceProfilePublic])
async def my_face_profiles(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    profiles = (
        await db.execute(
            select(FaceProfile)
            .where(FaceProfile.user_id == user.id)
            .order_by(FaceProfile.created_at.desc())
            .options(selectinload(FaceProfile.templates), selectinload(FaceProfile.user))
        )
    ).scalars().all()
    return [profile_public(item) for item in profiles]


@router.get("/admin/face-profiles", response_model=Page[FaceProfilePublic])
async def admin_face_profiles(
    profile_status: FaceProfileStatus | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    filters = [FaceProfile.status == profile_status] if profile_status else []
    total = await db.scalar(select(func.count()).select_from(FaceProfile).where(*filters))
    profiles = (
        await db.execute(
            select(FaceProfile)
            .where(*filters)
            .order_by(FaceProfile.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(FaceProfile.templates), selectinload(FaceProfile.user))
        )
    ).scalars().all()
    return Page(items=[profile_public(item) for item in profiles], total=total or 0, page=page, page_size=page_size)


@router.post("/admin/face-profiles/{profile_id}/live-verify", response_model=LiveVerifyResponse)
async def live_verify_profile(
    profile_id: UUID,
    files: list[UploadFile] = File(...),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    engine: BaseFaceEngine = Depends(get_face_engine),
):
    profile = (
        await db.execute(
            select(FaceProfile)
            .where(FaceProfile.id == profile_id)
            .options(selectinload(FaceProfile.templates), selectinload(FaceProfile.user))
        )
    ).scalar_one_or_none()
    if profile is None or profile.status != FaceProfileStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "只有待审批档案可以现场复验")
    frames, _ = await read_and_process_frames(files, engine)
    liveness = evaluate_liveness(frames, None)
    if not liveness.passed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, liveness.message)
    stored = []
    for template in profile.templates:
        raw = cipher.decrypt(template.encrypted_embedding, template.nonce, str(profile.id).encode("ascii"))
        vector = np.frombuffer(raw, dtype=np.float32).copy()
        if vector.size != template.dimension or vector.size != frames[0].embedding.size:
            continue
        vector /= np.linalg.norm(vector) + 1e-12
        stored.append(vector)
    if not stored:
        raise HTTPException(status.HTTP_409_CONFLICT, "待审批档案中没有可用的人脸模板，请重新录入")
    score = float(np.mean([max(float(vector @ frame.embedding) for vector in stored) for frame in frames]))
    verified = score >= settings.face_match_threshold
    if verified:
        profile.live_verified_at = utcnow()
        add_audit(db, action="FACE_PROFILE_LIVE_VERIFIED", target_type="face_profile", target_id=profile.id, actor_user_id=admin.id, after={"score": round(score, 4)})
        await db.commit()
    return LiveVerifyResponse(verified=verified, score=score, threshold=settings.face_match_threshold)


@router.post("/admin/face-profiles/{profile_id}/approve", response_model=FaceProfilePublic)
async def approve_profile(
    profile_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    profile = (
        await db.execute(
            select(FaceProfile)
            .where(FaceProfile.id == profile_id)
            .options(selectinload(FaceProfile.templates), selectinload(FaceProfile.user))
        )
    ).scalar_one_or_none()
    if profile is None or profile.status != FaceProfileStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "档案不是待审批状态")
    if profile.live_verified_at is None or profile.live_verified_at < utcnow() - timedelta(minutes=15):
        raise HTTPException(status.HTTP_409_CONFLICT, "请先在可信终端完成现场复验")
    now = utcnow()
    await db.execute(
        update(FaceProfile)
        .where(FaceProfile.user_id == profile.user_id, FaceProfile.status == FaceProfileStatus.ACTIVE)
        .values(status=FaceProfileStatus.REPLACED, reviewed_at=now)
    )
    profile.status = FaceProfileStatus.ACTIVE
    profile.approved_by_id = admin.id
    profile.reviewed_at = now
    add_audit(db, action="FACE_PROFILE_APPROVED", target_type="face_profile", target_id=profile.id, actor_user_id=admin.id, after={"status": FaceProfileStatus.ACTIVE.value})
    await db.commit()
    await face_cache.refresh(db)
    return profile_public(profile)


@router.post("/admin/face-profiles/{profile_id}/reject", response_model=FaceProfilePublic)
async def reject_profile(
    profile_id: UUID,
    payload: RejectFaceRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    profile = (
        await db.execute(
            select(FaceProfile)
            .where(FaceProfile.id == profile_id)
            .options(selectinload(FaceProfile.templates), selectinload(FaceProfile.user))
        )
    ).scalar_one_or_none()
    if profile is None or profile.status != FaceProfileStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "档案不是待审批状态")
    profile.status = FaceProfileStatus.REJECTED
    profile.rejection_reason = payload.reason
    profile.approved_by_id = admin.id
    profile.reviewed_at = utcnow()
    add_audit(db, action="FACE_PROFILE_REJECTED", target_type="face_profile", target_id=profile.id, actor_user_id=admin.id, after={"status": FaceProfileStatus.REJECTED.value}, reason=payload.reason)
    await db.commit()
    return profile_public(profile)


@router.post("/admin/face-profiles/{profile_id}/revoke", response_model=Message)
async def revoke_profile(
    profile_id: UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    profile = await db.get(FaceProfile, profile_id)
    if profile is None or profile.status != FaceProfileStatus.ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, "只有活动档案可以撤销")
    profile.status = FaceProfileStatus.REVOKED
    profile.reviewed_at = utcnow()
    add_audit(db, action="FACE_PROFILE_REVOKED", target_type="face_profile", target_id=profile.id, actor_user_id=admin.id, after={"status": FaceProfileStatus.REVOKED.value})
    await db.commit()
    await face_cache.refresh(db)
    return Message(message="人脸档案已撤销")
