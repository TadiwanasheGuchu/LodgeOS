"""Payments, allocations to invoices and refunds (ADR-0010).

Payments and refunds are records of money moving; neither is ever edited or deleted.
Allocations are append-only: releasing writes a negative row. A payment can be reversed
once (recorded in error, no money moved); a trigger allows only that change.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, new_uuid
from app.core.types import enum_check

Money = Numeric(12, 2)


class PaymentMethod(enum.StrEnum):
    CASH = "cash"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    MOBILE_MONEY = "mobile_money"
    OTHER = "other"


def _property_fk(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["property_id", "organisation_id"],
        ["properties.id", "properties.organisation_id"],
        name=f"fk_{table}_property_same_org",
        ondelete="RESTRICT",
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        _property_fk("payments"),
        ForeignKeyConstraint(
            ["reservation_id", "property_id"],
            ["reservations.id", "reservations.property_id"],
            name="fk_payments_reservation_same_property",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "idempotency_key", name="uq_payments_idempotency"),
        UniqueConstraint("id", "organisation_id", name="uq_payments_id_org"),
        CheckConstraint("amount > 0", name="positive"),
        CheckConstraint(enum_check("method", PaymentMethod), name="method"),
        CheckConstraint(
            "(reversed_at IS NULL) = (reversed_by IS NULL)"
            " AND (reversed_at IS NULL) = (reversal_reason IS NULL)",
            name="reversal_fields",
        ),
        Index("ix_payments_property_received", "property_id", "received_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    payer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    note: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    reversal_reason: Mapped[str | None] = mapped_column(Text)


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["payment_id", "organisation_id"],
            ["payments.id", "payments.organisation_id"],
            name="fk_payment_allocations_payment_same_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["invoice_id", "organisation_id"],
            ["invoices.id", "invoices.organisation_id"],
            name="fk_payment_allocations_invoice_same_org",
            ondelete="RESTRICT",
        ),
        CheckConstraint("amount <> 0", name="non_zero"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Positive allocates, negative releases.
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        _property_fk("refunds"),
        ForeignKeyConstraint(
            ["payment_id", "organisation_id"],
            ["payments.id", "payments.organisation_id"],
            name="fk_refunds_payment_same_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "idempotency_key", name="uq_refunds_idempotency"),
        CheckConstraint("amount > 0", name="positive"),
        CheckConstraint(enum_check("method", PaymentMethod), name="method"),
        Index("ix_refunds_property_refunded", "property_id", "refunded_on"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    refunded_on: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
