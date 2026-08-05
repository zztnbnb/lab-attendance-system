from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user_id: UUID, role: str) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("token type mismatch")
    return payload


def create_recognition_ticket(session_id: UUID, device_id: UUID, allowed_action: str) -> str:
    now = utcnow()
    payload = {
        "sub": str(session_id),
        "device": str(device_id),
        "action": allowed_action,
        "type": "recognition",
        "iat": now,
        "exp": now + timedelta(seconds=settings.recognition_ticket_seconds),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_recognition_ticket(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "recognition":
        raise jwt.InvalidTokenError("token type mismatch")
    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_device_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_device_secret(secret: str) -> str:
    value = f"{settings.device_credential_pepper}:{secret}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


class EmbeddingCipher:
    def __init__(self, key_b64: str | None = None):
        key = base64.b64decode(key_b64 or settings.embedding_key_b64)
        if len(key) != 32:
            raise ValueError("EMBEDDING_KEY_B64 解码后必须是 32 字节")
        self._aes = AESGCM(key)

    def encrypt(self, plaintext: bytes, associated_data: bytes) -> tuple[bytes, bytes]:
        nonce = secrets.token_bytes(12)
        return self._aes.encrypt(nonce, plaintext, associated_data), nonce

    def decrypt(self, ciphertext: bytes, nonce: bytes, associated_data: bytes) -> bytes:
        return self._aes.decrypt(nonce, ciphertext, associated_data)
