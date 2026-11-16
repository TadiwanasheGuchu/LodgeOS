import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


async def record(
    db: AsyncSession,
    *,
    action: str,
    organisation_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    data: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Append an audit event in the caller's transaction, so it commits or rolls back
    together with the change it describes. Never put secrets or full guest records in
    ``data``."""
    db.add(
        AuditLog(
            organisation_id=organisation_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            data=data or {},
            ip_address=ip_address,
        )
    )
    await db.flush()
