import asyncio
from uuid import uuid4

import numpy as np

from app.services.face_cache import CachedIdentity, FaceCacheSnapshot, FaceTemplateCache
from app.services.face_engine import FaceFrame


def test_face_cache_uses_batch_matrix_and_consistent_votes():
    first = CachedIdentity(uuid4(), "甲", "first", np.array([[1.0, 0.0], [0.98, 0.02]], dtype=np.float32))
    second = CachedIdentity(uuid4(), "乙", "second", np.array([[0.0, 1.0]], dtype=np.float32))
    cache = FaceTemplateCache()
    cache._identities = {first.user_id: first, second.user_id: second}
    cache._snapshot = FaceCacheSnapshot(
        identities=(first, second),
        template_matrix=np.ascontiguousarray(np.vstack([first.templates, second.templates]), dtype=np.float32),
        group_starts=np.array([0, 2], dtype=np.intp),
    )
    frames = [FaceFrame(np.array([1.0, 0.0], dtype=np.float32), 0.95, 0, 128, 180) for _ in range(4)]

    result = asyncio.run(cache.match(frames))

    assert result.identity is first
    assert result.votes == 4
    assert result.score > result.second_score
