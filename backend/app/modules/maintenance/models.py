"""Maintenance tickets and dated room blocks.

A room block takes one room out of sale for a range of nights (``start_date`` to
``end_date``, end exclusive like a stay). Blocks reduce sellable inventory only on those
nights, unlike the room's immediate ``maintenance_status = out_of_order``, which applies
until it is cleared.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid
from app.core.types import enum_check


class TicketStatus(enum.StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class TicketPriority(enum.StrEnum):
    LOW = "low"
    NORMAL = "normal"
    URGENT = "urgent"


class BlockStatus(enum.StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


def _property_fk(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["property_id", "organisation_id"],
        ["properties.id", "properties.organisation_id"],
        name=f"fk_{table}_property_same_org",
        ondelete="RESTRICT",
    )


class MaintenanceTicket(TimestampMixin, Base):
    __tablename__ = "maintenance_tickets"
    __table_args__ = (
        _property_fk("maintenance_tickets"),
        ForeignKeyConstraint(
            ["room_id", "property_id"],
            ["rooms.id", "rooms.property_id"],
            name="fk_maintenance_tickets_room_same_property",
            ondelete="RESTRICT",
        ),
        CheckConstraint(enum_check("status", TicketStatus), name="status"),
        CheckConstraint(enum_check("priority", TicketPriority), name="priority"),
        CheckConstraint(
            "(status IN ('resolved', 'cancelled')) = (closed_at IS NOT NULL)", name="closed_at"
        ),
        Index("ix_maintenance_tickets_open", "property_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # NULL for shared areas (kitchen, pool, generator).
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    location: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default=TicketPriority.NORMAL)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TicketStatus.OPEN)
    reported_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoomBlock(TimestampMixin, Base):
    __tablename__ = "room_blocks"
    __table_args__ = (
        _property_fk("room_blocks"),
        ForeignKeyConstraint(
            ["room_id", "property_id"],
            ["rooms.id", "rooms.property_id"],
            name="fk_room_blocks_room_same_property",
            ondelete="RESTRICT",
        ),
        CheckConstraint("end_date > start_date", name="dates"),
        CheckConstraint(enum_check("status", BlockStatus), name="status"),
        Index(
            "ix_room_blocks_active",
            "room_id",
            "start_date",
            "end_date",
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("maintenance_tickets.id", ondelete="RESTRICT"), index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)  # first night back in sale
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=BlockStatus.ACTIVE)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
