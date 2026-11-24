"""Reservations.

Guarantees, enforced in the database where possible:
- A physical room cannot be allocated to two active stays on the same night
  (exclusion constraint ``ex_reservation_rooms_no_double_booking``).
- Room-type inventory is checked inside a transaction that locks the room type row, so
  two concurrent bookings for the last room cannot both succeed (see service.py).
- Each booked room keeps the price breakdown it was sold at (``price_snapshot``), so later
  rate changes never alter an existing booking.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid
from app.core.types import enum_check

Money = Numeric(12, 2)


class ReservationStatus(enum.StrEnum):
    PROVISIONAL = "provisional"  # held, not yet confirmed by the guest
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


# Statuses that occupy inventory.
ACTIVE_STATUSES = (
    ReservationStatus.PROVISIONAL,
    ReservationStatus.CONFIRMED,
    ReservationStatus.CHECKED_IN,
)


class BookingSource(enum.StrEnum):
    PHONE = "phone"
    WALK_IN = "walk_in"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    OTA = "ota"
    CORPORATE = "corporate"
    OTHER = "other"


def _property_fk(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["property_id", "organisation_id"],
        ["properties.id", "properties.organisation_id"],
        name=f"fk_{table}_property_same_org",
        ondelete="RESTRICT",
    )


class Reservation(TimestampMixin, Base):
    __tablename__ = "reservations"
    __table_args__ = (
        _property_fk("reservations"),
        UniqueConstraint("organisation_id", "reference"),
        UniqueConstraint("id", "property_id", name="uq_reservations_id_property"),
        UniqueConstraint("organisation_id", "idempotency_key", name="uq_reservations_idempotency"),
        Index(
            "ix_reservations_hold_expiry",
            "hold_expires_at",
            postgresql_where=text("status = 'provisional' AND hold_expires_at IS NOT NULL"),
        ),
        CheckConstraint(enum_check("status", ReservationStatus), name="status"),
        CheckConstraint(enum_check("source", BookingSource), name="source"),
        CheckConstraint("check_out > check_in", name="dates"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso4217"),
        CheckConstraint(
            "(status = 'cancelled') = (cancellation_reason IS NOT NULL)", name="cancel_reason"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    guest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    # Website requests hold rooms until staff confirm or this time passes (ADR-0012).
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set by public bookings so a double submit creates one booking.
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    # From the guest portal (ADR-0013).
    guest_arrival_time: Mapped[str | None] = mapped_column(String(5))  # "HH:MM", local
    guest_message: Mapped[str | None] = mapped_column(Text)
    guest_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_request_reason: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )


class ReservationRoom(Base):
    """One room on a reservation: booked as a room type, with the physical room allocated
    now or later. Dates are copied from the reservation so the database can enforce
    non-overlapping allocations on this table alone."""

    __tablename__ = "reservation_rooms"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reservation_id", "property_id"],
            ["reservations.id", "reservations.property_id"],
            name="fk_reservation_rooms_reservation_same_property",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["room_type_id", "property_id"],
            ["room_types.id", "room_types.property_id"],
            name="fk_reservation_rooms_room_type_same_property",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["room_id", "property_id"],
            ["rooms.id", "rooms.property_id"],
            name="fk_reservation_rooms_room_same_property",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["rate_plan_id", "property_id"],
            ["rate_plans.id", "rate_plans.property_id"],
            name="fk_reservation_rooms_rate_plan_same_property",
            ondelete="RESTRICT",
        ),
        _property_fk("reservation_rooms"),
        CheckConstraint("check_out > check_in", name="dates"),
        CheckConstraint("adults >= 1 AND children >= 0", name="guests"),
        # Inventory counts read active stays by property, room type and dates.
        Index(
            "ix_reservation_rooms_inventory",
            "property_id",
            "room_type_id",
            "check_in",
            "check_out",
            postgresql_where=text("status IN ('provisional', 'confirmed', 'checked_in')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    room_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    room_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    rate_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    # Mirrors the reservation status so inventory and the exclusion constraint can tell
    # active stays from cancelled ones without a join.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    adults: Mapped[int] = mapped_column(Integer, nullable=False)
    children: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    price_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ReservationStatusChange(Base):
    """Append-only history of status changes."""

    __tablename__ = "reservation_status_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reservation_id", "property_id"],
            ["reservations.id", "reservations.property_id"],
            name="fk_reservation_status_history_reservation",
            ondelete="CASCADE",
        ),
        _property_fk("reservation_status_history"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
