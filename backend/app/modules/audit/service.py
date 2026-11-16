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


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)  # UUIDs, times, dates, enums


def apply_changes(entity: object, changes: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Set ``changes`` on ``entity`` and return {"before": ..., "after": ...} for the
    fields that actually changed, ready for an audit record."""
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for key, value in changes.items():
        old = getattr(entity, key)
        if old != value:
            before[key] = _json_safe(old)
            after[key] = _json_safe(value)
            setattr(entity, key, value)
    return {"before": before, "after": after}
