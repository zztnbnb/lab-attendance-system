from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    new_refresh_token,
    token_hash,
    utcnow,
    verify_password,
)
from app.db.session import get_db
from app.models.entities import AuthSession, Role, User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.schemas.common import Message
from app.services.audit import add_audit


router = APIRouter(prefix="/auth", tags=["认证"])
COOKIE_NAME = "lab_refresh_token"


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=f"{settings.api_prefix}/auth",
    )


async def issue_tokens(db: AsyncSession, user: User, response: Response, family_id=None) -> TokenResponse:
    refresh = new_refresh_token()
    session = AuthSession(
        user_id=user.id,
        family_id=family_id or uuid4(),
        token_hash=token_hash(refresh),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
    )
    db.add(session)
    await db.commit()
    set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        expires_in=settings.access_token_minutes * 60,
        user=UserPublic.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已停用")
    add_audit(db, action="AUTH_LOGIN", target_type="user", target_id=user.id, actor_user_id=user.id)
    return await issue_tokens(db, user, response)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    student_id = payload.student_id.strip()
    exists = await db.scalar(
        select(func.count()).select_from(User).where(
            or_(User.username == student_id, User.identifier == student_id)
        )
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "该学号已经注册，请直接登录或联系管理员")
    user = User(
        username=student_id,
        identifier=student_id,
        real_name=payload.real_name.strip(),
        password_hash=hash_password(payload.password),
        role=Role.USER,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    add_audit(db, action="AUTH_REGISTERED", target_type="user", target_id=user.id, actor_user_id=user.id, after={"username": student_id})
    await db.commit()
    await db.refresh(user)
    return await issue_tokens(db, user, response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "刷新令牌缺失")
    session = (
        await db.execute(select(AuthSession).where(AuthSession.token_hash == token_hash(refresh_token)).with_for_update())
    ).scalar_one_or_none()
    now = utcnow()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        if session is not None:
            await db.execute(
                update(AuthSession)
                .where(AuthSession.family_id == session.family_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "刷新令牌无效或已过期")
    session.revoked_at = now
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return await issue_tokens(db, user, response, session.family_id)


@router.post("/logout", response_model=Message)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token:
        session = (
            await db.execute(select(AuthSession).where(AuthSession.token_hash == token_hash(refresh_token)))
        ).scalar_one_or_none()
        if session and session.revoked_at is None:
            session.revoked_at = utcnow()
            await db.commit()
    response.delete_cookie(COOKIE_NAME, path=f"{settings.api_prefix}/auth")
    return Message(message="已退出登录")


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=Message)
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前密码错误")
    user.password_hash = hash_password(payload.new_password)
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    add_audit(db, action="AUTH_PASSWORD_CHANGED", target_type="user", target_id=user.id, actor_user_id=user.id)
    await db.commit()
    return Message(message="密码已修改，请重新登录")
