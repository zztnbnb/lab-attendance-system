import hashlib
from pathlib import Path

import pytest

from app.models.entities import ChallengeType
from app.services.face_engine import (
    FaceEngineUnavailable,
    StubFaceEngine,
    evaluate_liveness,
    prepare_opencv_model_path,
    verify_model_checksum,
)


def test_model_checksum_validation(tmp_path: Path):
    model = tmp_path / "model.onnx"
    model.write_bytes(b"pinned-model")
    verify_model_checksum(model, hashlib.sha256(b"pinned-model").hexdigest())
    with pytest.raises(FaceEngineUnavailable, match="校验和不匹配"):
        verify_model_checksum(model, "0" * 64)


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows OpenCV path compatibility")
def test_non_ascii_model_path_is_mirrored(tmp_path: Path):
    model = tmp_path / "中文目录" / "model.onnx"
    model.parent.mkdir()
    model.write_bytes(b"pinned-model")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()

    prepared = prepare_opencv_model_path(model, digest)

    prepared.resolve().as_posix().encode("ascii")
    assert prepared.read_bytes() == model.read_bytes()


def test_static_scan_accepts_consistent_clear_frames():
    engine = StubFaceEngine()
    frames = [engine.process(b"alice|front") for _ in range(4)]

    result = evaluate_liveness(frames, ChallengeType.STATIC)

    assert result.passed is True
    assert result.message == "静态人脸核验通过"
