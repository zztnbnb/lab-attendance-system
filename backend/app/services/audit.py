from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditLog


def add_audit(
    db: AsyncSession,
    *,
    action: str,
    target_type: str,
    target_id: UUID | str,
    actor_user_id: UUID | None = None,
    actor_device_id: UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        actor_user_id=actor_user_id,
        actor_device_id=actor_device_id,
        before_data=before,
        after_data=after,
        reason=reason,
    )
    db.add(log)
    return log
