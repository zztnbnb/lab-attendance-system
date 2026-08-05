from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import EmbeddingCipher
from app.models.entities import FaceProfile, FaceProfileStatus, User
from app.services.face_engine import FaceFrame


@dataclass(slots=True)
class CachedIdentity:
    user_id: UUID
    real_name: str
    username: str
    templates: np.ndarray


@dataclass(slots=True)
class FaceCacheSnapshot:
    """Immutable arrays used by the recognition hot path.

    Template rows are grouped by identity.  This makes one matrix multiply
    sufficient for every captured frame while retaining the existing rule of
    using each user's best matching enrollment template.
    """

    identities: tuple[CachedIdentity, ...]
    template_matrix: np.ndarray
    group_starts: np.ndarray


@dataclass(slots=True)
class MatchResult:
    identity: CachedIdentity | None
    score: float
    second_score: float
    votes: int


class FaceTemplateCache:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._identities: dict[UUID, CachedIdentity] = {}
        self._snapshot = FaceCacheSnapshot(
            identities=(),
            template_matrix=np.empty((0, 0), dtype=np.float32),
            group_starts=np.empty(0, dtype=np.intp),
        )
        self._cipher = EmbeddingCipher()

    @property
    def size(self) -> int:
        return len(self._identities)

    async def refresh(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(FaceProfile)
            .join(FaceProfile.user)
            .where(FaceProfile.status == FaceProfileStatus.ACTIVE, User.is_active.is_(True))
            .options(selectinload(FaceProfile.templates), selectinload(FaceProfile.user))
        )
        identities: dict[UUID, CachedIdentity] = {}
        expected_dimension: int | None = None
        for profile in result.scalars().unique():
            vectors: list[np.ndarray] = []
            for template in profile.templates:
                raw = self._cipher.decrypt(
                    template.encrypted_embedding,
                    template.nonce,
                    str(profile.id).encode("ascii"),
                )
                vector = np.frombuffer(raw, dtype=np.float32).copy()
                if vector.size != template.dimension:
                    continue
                vector /= np.linalg.norm(vector) + 1e-12
                vectors.append(vector)
            if not vectors:
                continue
            dimension = vectors[0].size
            if any(vector.size != dimension for vector in vectors):
                continue
            # The active engine has one embedding dimension.  Ignore an old or
            # corrupt profile rather than making every recognition fail.
            if expected_dimension is None:
                expected_dimension = dimension
            if dimension != expected_dimension:
                continue
            identities[profile.user_id] = CachedIdentity(
                profile.user_id,
                profile.user.real_name,
                profile.user.username,
                np.ascontiguousarray(np.vstack(vectors), dtype=np.float32),
            )

        ordered = tuple(identities.values())
        if ordered:
            template_matrix = np.ascontiguousarray(
                np.vstack([identity.templates for identity in ordered]), dtype=np.float32
            )
            group_starts = np.cumsum(
                np.array([0, *[identity.templates.shape[0] for identity in ordered[:-1]]], dtype=np.intp)
            )
            template_matrix.setflags(write=False)
            group_starts.setflags(write=False)
        else:
            template_matrix = np.empty((0, 0), dtype=np.float32)
            group_starts = np.empty(0, dtype=np.intp)

        snapshot = FaceCacheSnapshot(ordered, template_matrix, group_starts)
        async with self._lock:
            self._identities = identities
            self._snapshot = snapshot
        return len(identities)

    async def match(self, frames: list[FaceFrame]) -> MatchResult:
        async with self._lock:
            snapshot = self._snapshot
        if not snapshot.identities or not frames:
            return MatchResult(None, 0.0, 0.0, 0)

        embeddings = np.ascontiguousarray(np.vstack([frame.embedding for frame in frames]), dtype=np.float32)
        if embeddings.shape[1] != snapshot.template_matrix.shape[1]:
            return MatchResult(None, 0.0, 0.0, 0)

        # scores[frame, template].  The template rows of a person are
        # contiguous, so reduceat yields each person's best template score.
        scores = embeddings @ snapshot.template_matrix.T
        user_scores = np.maximum.reduceat(scores, snapshot.group_starts, axis=1)
        mean_scores = user_scores.mean(axis=0)
        ranking = np.argsort(mean_scores)[::-1]
        best_index = int(ranking[0])
        best_score = float(mean_scores[best_index])
        second_score = float(mean_scores[int(ranking[1])]) if len(ranking) > 1 else 0.0
        frame_winners = np.argmax(user_scores, axis=1)
        votes = int(np.count_nonzero(frame_winners == best_index))
        required_votes = max(2, (len(frames) * 3 + 4) // 5)
        accepted = (
            best_score >= settings.face_match_threshold
            and best_score - second_score >= settings.face_match_margin
            and votes >= required_votes
        )
        identity = snapshot.identities[best_index] if accepted else None
        return MatchResult(identity, best_score, second_score, votes)


face_cache = FaceTemplateCache()
