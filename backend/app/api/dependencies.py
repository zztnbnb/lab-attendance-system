from __future__ import annotations

import hmac
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, hash_device_secret, utcnow
from app.db.session import get_db
from app.models.entities import KioskDevice, Role, User


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录状态无效") from exc
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


async def get_device(
    x_device_code: str = Header(alias="X-Device-Code"),
    x_device_key: str = Header(alias="X-Device-Key"),
    db: AsyncSession = Depends(get_db),
) -> KioskDevice:
    device = (
        await db.execute(select(KioskDevice).where(KioskDevice.code == x_device_code.upper()))
    ).scalar_one_or_none()
    if device is None or not device.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "终端未注册或已停用")
    supplied = hash_device_secret(x_device_key)
    if not hmac.compare_digest(device.credential_hash, supplied):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "终端凭证无效")
    device.last_seen_at = utcnow()
    await db.commit()
    return device


def get_face_engine(request: Request):
    engine = getattr(request.app.state, "face_engine", None)
    if engine is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "人脸识别模型尚未配置")
    return engine
