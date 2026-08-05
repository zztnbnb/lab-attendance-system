from pydantic import BaseModel, Field

from app.models.entities import Role


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]+$", min_length=3, max_length=64)
    real_name: str = Field(min_length=1, max_length=100)
    identifier: str | None = Field(default=None, max_length=64)
    password: str = Field(min_length=10, max_length=128)
    role: Role = Role.USER


class UserUpdate(BaseModel):
    real_name: str | None = Field(default=None, min_length=1, max_length=100)
    identifier: str | None = Field(default=None, max_length=64)
    role: Role | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)
