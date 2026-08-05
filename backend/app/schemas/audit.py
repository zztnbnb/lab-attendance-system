from datetime import datetime
from uuid import UUID

from app.schemas.common import ORMModel


class AuditLogPublic(ORMModel):
    id: UUID
    actor_user_id: UUID | None
    actor_device_id: UUID | None
    action: str
    target_type: str
    target_id: str
    before_data: dict | None
    after_data: dict | None
    reason: str | None
    created_at: datetime
