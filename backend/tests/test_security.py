import numpy as np

from app.core.security import EmbeddingCipher, create_access_token, decode_access_token
from app.services.face_engine import StubFaceEngine


def test_embedding_cipher_roundtrip():
    cipher = EmbeddingCipher()
    raw = np.arange(128, dtype=np.float32).tobytes()
    encrypted, nonce = cipher.encrypt(raw, b"profile-id")
    assert encrypted != raw
    assert cipher.decrypt(encrypted, nonce, b"profile-id") == raw


def test_access_token_roundtrip():
    from uuid import uuid4

    user_id = uuid4()
    token = create_access_token(user_id, "USER")
    assert decode_access_token(token)["sub"] == str(user_id)


def test_stub_engine_same_identity_different_pose():
    engine = StubFaceEngine()
    left = engine.process(b"alice|left")
    right = engine.process(b"alice|right")
    assert float(left.embedding @ right.embedding) > 0.999
    assert left.yaw_proxy < 0 < right.yaw_proxy
