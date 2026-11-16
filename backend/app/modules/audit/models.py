import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, new_uuid


class AuditLog(Base):
    """Append-only record of security-relevant and business-relevant actions.

    The application role is granted INSERT and SELECT only, so rows cannot be changed
    or removed through the API.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_org_created", "organisation_id", "created_at"),)
    # Do not read server defaults back with INSERT ... RETURNING: PostgreSQL applies the
    # SELECT policy to returned rows, and events without an organisation are deliberately
    # unreadable by the application role.
    __mapper_args__ = {"eager_defaults": False}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    # Null for events that happen outside a tenant, such as a failed sign-in.
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organisations.id", ondelete="RESTRICT")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
