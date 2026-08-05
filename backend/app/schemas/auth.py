from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.entities import Role
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class UserPublic(ORMModel):
    id: UUID
    username: str
    real_name: str
    identifier: str | None
    role: Role
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)
