"""Invoices, credit notes and their gapless numbering (ADR-0009).

Issued invoices and all credit notes are immutable; database triggers enforce it. Every
line satisfies net + taxes = total, and document totals are the sums of their lines.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid
from app.core.types import enum_check

Money = Numeric(12, 2)


class InvoiceStatus(enum.StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    DISCARDED = "discarded"


class ItemKind(enum.StrEnum):
    ACCOMMODATION = "accommodation"
    EXTRA = "extra"


class DocumentKind(enum.StrEnum):
    INVOICE = "invoice"
    CREDIT_NOTE = "credit_note"


PREFIX = {DocumentKind.INVOICE: "INV", DocumentKind.CREDIT_NOTE: "CN"}


def _property_fk(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["property_id", "organisation_id"],
        ["properties.id", "properties.organisation_id"],
        name=f"fk_{table}_property_same_org",
        ondelete="RESTRICT",
    )


def _sums() -> CheckConstraint:
    return CheckConstraint("net_amount + tax_amount = total_amount", name="sums")


class DocumentSequence(Base):
    """Next number per organisation and document kind; locked while a document is issued."""

    __tablename__ = "document_sequences"
    __table_args__ = (CheckConstraint(enum_check("kind", DocumentKind), name="kind"),)

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="RESTRICT"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    next_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        _property_fk("invoices"),
        ForeignKeyConstraint(
            ["reservation_id", "property_id"],
            ["reservations.id", "reservations.property_id"],
            name="fk_invoices_reservation_same_property",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "number", name="uq_invoices_org_number"),
        UniqueConstraint("id", "organisation_id", name="uq_invoices_id_org"),
        CheckConstraint(enum_check("status", InvoiceStatus), name="status"),
        CheckConstraint(
            "(status = 'issued') = (number IS NOT NULL AND issue_date IS NOT NULL"
            " AND issued_at IS NOT NULL)",
            name="issued_fields",
        ),
        CheckConstraint("net_total + tax_total = total", name="sums"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    guest_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("guests.id", ondelete="RESTRICT"))
    number: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=InvoiceStatus.DRAFT)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    issue_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    bill_to_name: Mapped[str] = mapped_column(String(200), nullable=False)
    bill_to_details: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    net_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0.00"))
    tax_total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal("0.00"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["invoice_id", "organisation_id"],
            ["invoices.id", "invoices.organisation_id"],
            name="fk_invoice_items_invoice_same_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "invoice_id", name="uq_invoice_items_id_invoice"),
        CheckConstraint(enum_check("kind", ItemKind), name="kind"),
        CheckConstraint("quantity > 0", name="quantity"),
        _sums(),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    prices_include_tax: Mapped[bool] = mapped_column(Boolean, nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    # [{name, rate_percent, amount}] as strings: the taxes as charged on this line.
    taxes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    reservation_room_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reservation_rooms.id", ondelete="RESTRICT"), index=True
    )
    service_from: Mapped[date | None] = mapped_column(Date)
    service_to: Mapped[date | None] = mapped_column(Date)


class CreditNote(Base):
    __tablename__ = "credit_notes"
    __table_args__ = (
        _property_fk("credit_notes"),
        ForeignKeyConstraint(
            ["invoice_id", "organisation_id"],
            ["invoices.id", "invoices.organisation_id"],
            name="fk_credit_notes_invoice_same_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "number", name="uq_credit_notes_org_number"),
        UniqueConstraint("id", "organisation_id", name="uq_credit_notes_id_org"),
        CheckConstraint("total > 0", name="positive"),
        CheckConstraint("net_total + tax_total = total", name="sums"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    net_total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class CreditNoteItem(Base):
    __tablename__ = "credit_note_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["credit_note_id", "organisation_id"],
            ["credit_notes.id", "credit_notes.organisation_id"],
            name="fk_credit_note_items_credit_note_same_org",
            ondelete="RESTRICT",
        ),
        CheckConstraint("total_amount > 0", name="positive"),
        _sums(),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    credit_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    invoice_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoice_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    taxes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
