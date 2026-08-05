from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.models.entities import ChallengeType


MODEL_VERSION = "opencv-sface-2021dec-yunet-2023mar"


class FaceEngineError(RuntimeError):
    code = "FACE_ENGINE_ERROR"


class FaceEngineUnavailable(FaceEngineError):
    code = "FACE_ENGINE_UNAVAILABLE"


class NoFaceDetected(FaceEngineError):
    code = "NO_FACE"


class MultipleFacesDetected(FaceEngineError):
    code = "MULTIPLE_FACES"


class FaceQualityError(FaceEngineError):
    code = "QUALITY_FAILED"


class LivenessError(FaceEngineError):
    code = "LIVENESS_FAILED"


@dataclass(slots=True)
class FaceFrame:
    embedding: np.ndarray
    quality: float
    yaw_proxy: float
    brightness: float
    sharpness: float
    face_box: tuple[float, float, float, float] | None = None


@dataclass(slots=True)
class LivenessResult:
    passed: bool
    score: float
    message: str


class BaseFaceEngine:
    ready: bool = False
    model_version: str = MODEL_VERSION

    def process(self, content: bytes) -> FaceFrame:
        raise NotImplementedError


class StubFaceEngine(BaseFaceEngine):
    """仅供自动化测试使用，生产配置禁止使用。"""

    ready = True
    model_version = "stub-test-only"

    def process(self, content: bytes) -> FaceFrame:
        if not content:
            raise NoFaceDetected("空图片")
        identity, _, pose = content.partition(b"|")
        digest = hashlib.sha512(identity).digest()
        vector = np.frombuffer(digest * 2, dtype=np.uint8).astype(np.float32)[:128]
        vector = vector - vector.mean()
        vector /= np.linalg.norm(vector) + 1e-12
        if pose == b"left":
            yaw = -0.24
        elif pose == b"right":
            yaw = 0.24
        else:
            yaw = 0.0
        return FaceFrame(vector, 0.95, yaw, 128.0, 180.0, (0.28, 0.16, 0.44, 0.62))


def verify_model_checksum(path: Path, expected: str | None) -> None:
    if not expected:
        return
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if not hmac.compare_digest(actual.lower(), expected.strip().lower()):
        raise FaceEngineUnavailable(f"模型校验和不匹配: {path.name}")


def prepare_opencv_model_path(path: Path, expected: str | None) -> Path:
    """Mirror models to an ASCII path for OpenCV on Windows.

    OpenCV's Windows model loaders may reject otherwise valid files when any
    directory in the path contains non-ASCII characters. The checked project
    model remains the source of truth; the mirror is content-addressed and can
    be recreated at any time.
    """
    verify_model_checksum(path, expected)
    if os.name != "nt":
        return path
    try:
        str(path).encode("ascii")
        return path
    except UnicodeEncodeError:
        fingerprint = expected.strip().lower() if expected else hashlib.sha256(path.read_bytes()).hexdigest()
        cache_dir = Path(tempfile.gettempdir()) / "labtime-face-models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached = cache_dir / f"{fingerprint[:16]}-{path.name}"
        if not cached.is_file() or cached.stat().st_size != path.stat().st_size:
            shutil.copyfile(path, cached)
        verify_model_checksum(cached, fingerprint)
        return cached


class OpenCVFaceEngine(BaseFaceEngine):
    model_version = MODEL_VERSION

    def __init__(self, detector_path: Path, recognizer_path: Path, detector_sha256: str | None = None, recognizer_sha256: str | None = None):
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - dependency is required in deployment
            raise FaceEngineUnavailable("未安装 opencv-python-headless") from exc
        if not detector_path.is_file() or not recognizer_path.is_file():
            missing = [str(p) for p in (detector_path, recognizer_path) if not p.is_file()]
            raise FaceEngineUnavailable(f"缺少人脸模型: {', '.join(missing)}")
        detector_path = prepare_opencv_model_path(detector_path, detector_sha256)
        recognizer_path = prepare_opencv_model_path(recognizer_path, recognizer_sha256)
        self.cv2 = cv2
        try:
            self.detector = cv2.FaceDetectorYN.create(str(detector_path), "", (320, 320), 0.85, 0.3, 5000)
            self.recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")
        except cv2.error as exc:
            raise FaceEngineUnavailable(f"OpenCV 无法加载人脸模型: {exc}") from exc
        self.ready = True

    def process(self, content: bytes) -> FaceFrame:
        cv2 = self.cv2
        encoded = np.frombuffer(content, np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image is None:
            raise FaceQualityError("无法解码图片")
        height, width = image.shape[:2]
        if width < 240 or height < 240:
            raise FaceQualityError("画面分辨率过低")

        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(image)
        if faces is None or len(faces) == 0:
            raise NoFaceDetected("未检测到人脸")
        if len(faces) != 1:
            raise MultipleFacesDetected("画面中必须只有一张人脸")

        face = faces[0]
        x, y, w, h = face[:4]
        face_ratio = (w * h) / float(width * height)
        if face_ratio < 0.07:
            raise FaceQualityError("请靠近摄像头")

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
        if sharpness < 45:
            raise FaceQualityError("画面模糊，请保持静止")
        if brightness < 45 or brightness > 220:
            raise FaceQualityError("光线过暗或过亮")

        aligned = self.recognizer.alignCrop(image, face)
        embedding = self.recognizer.feature(aligned).flatten().astype(np.float32)
        embedding /= np.linalg.norm(embedding) + 1e-12

        right_eye_x, left_eye_x, nose_x = float(face[4]), float(face[6]), float(face[8])
        eye_midpoint = (right_eye_x + left_eye_x) / 2.0
        eye_distance = max(abs(left_eye_x - right_eye_x), 1.0)
        yaw_proxy = (nose_x - eye_midpoint) / eye_distance
        detection_score = float(face[-1])
        blur_score = min(sharpness / 180.0, 1.0)
        exposure_score = 1.0 - min(abs(brightness - 128.0) / 128.0, 1.0)
        quality = max(0.0, min(1.0, detection_score * 0.6 + blur_score * 0.2 + exposure_score * 0.2))
        # Keep only a normalized rectangle for the transient API response.  The
        # original image remains request-local and is never persisted.
        face_box = (
            max(0.0, min(1.0, float(x) / width)),
            max(0.0, min(1.0, float(y) / height)),
            max(0.0, min(1.0, float(w) / width)),
            max(0.0, min(1.0, float(h) / height)),
        )
        return FaceFrame(embedding, quality, yaw_proxy, brightness, sharpness, face_box)


def build_face_engine() -> tuple[BaseFaceEngine | None, str]:
    if settings.face_engine == "stub":
        if settings.is_production:
            raise RuntimeError("生产环境禁止使用 StubFaceEngine")
        return StubFaceEngine(), "ready:test-stub"
    try:
        engine = OpenCVFaceEngine(
            settings.yunet_model_path,
            settings.sface_model_path,
            settings.yunet_model_sha256,
            settings.sface_model_sha256,
        )
        return engine, "ready:opencv"
    except FaceEngineUnavailable as exc:
        if settings.require_face_engine:
            raise
        return None, f"unavailable:{exc}"


def evaluate_liveness(frames: list[FaceFrame], challenge: ChallengeType | None) -> LivenessResult:
    if len(frames) < settings.min_face_templates:
        return LivenessResult(False, 0.0, "有效帧数量不足")

    yaws = np.array([frame.yaw_proxy for frame in frames], dtype=np.float32)
    qualities = np.array([frame.quality for frame in frames], dtype=np.float32)
    pose_range = float(yaws.max() - yaws.min())
    diversity_score = min(pose_range / 0.18, 1.0)
    quality_score = float(qualities.mean())

    if challenge == ChallengeType.STATIC:
        embeddings = np.vstack([frame.embedding for frame in frames])
        similarities = embeddings @ embeddings.T
        upper_triangle = similarities[np.triu_indices(len(frames), k=1)]
        consistency = float(upper_triangle.mean()) if upper_triangle.size else 0.0
        consistency_score = min(max((consistency - 0.45) / 0.40, 0.0), 1.0)
        score = quality_score * 0.60 + consistency_score * 0.40
        passed = quality_score >= 0.55 and consistency >= 0.55
        return LivenessResult(passed, score, "静态人脸核验通过" if passed else "请正对摄像头并保持画面清晰")
    if challenge == ChallengeType.TURN_LEFT:
        challenge_score = min(max(float(-yaws.min()) / 0.13, 0.0), 1.0)
    elif challenge == ChallengeType.TURN_RIGHT:
        challenge_score = min(max(float(yaws.max()) / 0.13, 0.0), 1.0)
    else:
        challenge_score = diversity_score

    score = quality_score * 0.35 + diversity_score * 0.25 + challenge_score * 0.40
    passed = diversity_score >= 0.35 and challenge_score >= 0.45 and quality_score >= 0.55
    if settings.require_passive_liveness and not settings.passive_liveness_model_path:
        return LivenessResult(False, 0.0, "系统要求静默活体模型，但尚未配置模型文件")
    return LivenessResult(passed, score, "活体检测通过" if passed else "未完成指定动作或画面质量不足")
