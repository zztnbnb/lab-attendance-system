from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "实验室人脸识别打卡系统"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite+aiosqlite:///{(BACKEND_DIR / 'data' / 'lab_attendance.db').as_posix()}"
    auto_create_tables: bool = True

    jwt_secret: str = "dev-only-change-this-jwt-secret-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    recognition_ticket_seconds: int = 60
    cookie_secure: bool = False
    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    embedding_key_b64: str = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    key_version: int = 1

    face_engine: str = "opencv"
    require_face_engine: bool = False
    yunet_model_path: Path = PROJECT_DIR / "models" / "face_detection_yunet_2023mar.onnx"
    sface_model_path: Path = PROJECT_DIR / "models" / "face_recognition_sface_2021dec.onnx"
    yunet_model_sha256: str | None = None
    sface_model_sha256: str | None = None
    passive_liveness_model_path: Path | None = None
    require_passive_liveness: bool = False
    face_match_threshold: float = 0.45
    face_match_margin: float = 0.05
    min_face_templates: int = 3
    max_upload_bytes: int = 1_500_000
    recognition_frames: int = 5

    missing_checkout_hours: int = 24
    timezone: str = "Asia/Shanghai"

    initial_admin_username: str = "admin"
    initial_admin_password: str = "ChangeMe123!"
    initial_admin_real_name: str = "系统管理员"
    device_credential_pepper: str = "dev-only-change-device-pepper"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_production_safety(self) -> None:
        if not self.is_production:
            return
        unsafe = []
        if self.jwt_secret.startswith("dev-only"):
            unsafe.append("JWT_SECRET")
        if self.device_credential_pepper.startswith("dev-only"):
            unsafe.append("DEVICE_CREDENTIAL_PEPPER")
        if self.initial_admin_password == "ChangeMe123!":
            unsafe.append("INITIAL_ADMIN_PASSWORD")
        if not self.cookie_secure:
            unsafe.append("COOKIE_SECURE")
        if not self.yunet_model_sha256:
            unsafe.append("YUNET_MODEL_SHA256")
        if not self.sface_model_sha256:
            unsafe.append("SFACE_MODEL_SHA256")
        if unsafe:
            raise RuntimeError(f"生产配置不安全，请设置: {', '.join(unsafe)}")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production_safety()
    return settings


settings = get_settings()
