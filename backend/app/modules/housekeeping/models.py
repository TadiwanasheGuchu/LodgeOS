"""Housekeeping work for one room on one day.

The day's list is derived from reservations (departures, stay-overs, arrivals) and room
status; a task row is only written once someone acts on a room that day: takes it, starts,
finishes, or records that the guest declined service. One row per room per day.
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid
from app.core.types import enum_check


class TaskKind(enum.StrEnum):
    DEPARTURE = "departure"  # full clean after the guest leaves
    STAYOVER = "stayover"  # service while the guest stays
    ARRIVAL = "arrival"  # vacant room to be ready for an arrival
    VACANT = "vacant"  # vacant dirty room, nobody arriving


class TaskStatus(enum.StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DECLINED = "declined"  # guest declined service or do-not-disturb


class HousekeepingTask(TimestampMixin, Base):
    __tablename__ = "housekeeping_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["property_id", "organisation_id"],
            ["properties.id", "properties.organisation_id"],
            name="fk_housekeeping_tasks_property_same_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["room_id", "property_id"],
            ["rooms.id", "rooms.property_id"],
            name="fk_housekeeping_tasks_room_same_property",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("room_id", "task_date", name="uq_housekeeping_tasks_room_day"),
        CheckConstraint(enum_check("kind", TaskKind), name="kind"),
        CheckConstraint(enum_check("status", TaskStatus), name="status"),
        CheckConstraint(
            "(status IN ('done', 'declined')) = (completed_at IS NOT NULL)", name="completed_at"
        ),
        CheckConstraint("status <> 'declined' OR note IS NOT NULL", name="declined_note"),
        Index("ix_housekeeping_tasks_property_day", "property_id", "task_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    room_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_date: Mapped[date] = mapped_column(Date, nullable=False)
    # The kind when first acted on, kept for reporting even if bookings change later.
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TaskStatus.PENDING)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    note: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
