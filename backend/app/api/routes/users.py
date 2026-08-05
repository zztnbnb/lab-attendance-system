from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.entities import User
from app.schemas.auth import UserPublic
from app.schemas.common import Message, Page
from app.schemas.users import PasswordReset, UserCreate, UserUpdate
from app.services.audit import add_audit


router = APIRouter(prefix="/admin/users", tags=["管理员-用户"])


@router.get("", response_model=Page[UserPublic])
async def list_users(
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if q:
        keyword = f"%{q}%"
        filters.append(or_(User.username.ilike(keyword), User.real_name.ilike(keyword), User.identifier.ilike(keyword)))
    total = await db.scalar(select(func.count()).select_from(User).where(*filters))
    users = (
        await db.execute(
            select(User).where(*filters).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    return Page(items=[UserPublic.model_validate(item) for item in users], total=total or 0, page=page, page_size=page_size)


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    exists = await db.scalar(
        select(func.count()).select_from(User).where(
            or_(User.username == payload.username, User.identifier == payload.identifier) if payload.identifier else User.username == payload.username
        )
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "用户名或学号/工号已存在")
    user = User(
        username=payload.username,
        real_name=payload.real_name,
        identifier=payload.identifier,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    add_audit(db, action="USER_CREATED", target_type="user", target_id=user.id, actor_user_id=admin.id, after={"username": user.username, "role": user.role.value})
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    before = {"real_name": user.real_name, "identifier": user.identifier, "role": user.role.value, "is_active": user.is_active}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    after = {"real_name": user.real_name, "identifier": user.identifier, "role": user.role.value, "is_active": user.is_active}
    add_audit(db, action="USER_UPDATED", target_type="user", target_id=user.id, actor_user_id=admin.id, before=before, after=after)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=Message)
async def reset_password(
    user_id: UUID,
    payload: PasswordReset,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    user.password_hash = hash_password(payload.new_password)
    add_audit(db, action="USER_PASSWORD_RESET", target_type="user", target_id=user.id, actor_user_id=admin.id)
    await db.commit()
    return Message(message="密码已重置")
