"""Point of sale (ADR-0015): outlets, catalogue items and settled sales."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from app.modules.properties.models import RecordStatus

Money = Numeric(12, 2)


class Settlement(enum.StrEnum):
    ROOM = "room"
    PAID = "paid"


def _property_fk(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["property_id", "organisation_id"],
        ["properties.id", "properties.organisation_id"],
        name=f"fk_{table}_property_same_org",
        ondelete="RESTRICT",
    )


class PosOutlet(TimestampMixin, Base):
    __tablename__ = "pos_outlets"
    __table_args__ = (
        _property_fk("pos_outlets"),
        UniqueConstraint("property_id", "name", name="uq_pos_outlets_property_name"),
        UniqueConstraint("id", "property_id", name="uq_pos_outlets_id_property"),
        CheckConstraint(enum_check("status", RecordStatus), name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecordStatus.ACTIVE)


class Service(TimestampMixin, Base):
    """A sellable item: a drink, a meal, an activity, a curio."""

    __tablename__ = "services"
    __table_args__ = (
        _property_fk("services"),
        ForeignKeyConstraint(
            ["outlet_id", "property_id"],
            ["pos_outlets.id", "pos_outlets.property_id"],
            name="fk_services_outlet_same_property",
            ondelete="RESTRICT",
        ),
        CheckConstraint("price > 0", name="price"),
        CheckConstraint(enum_check("status", RecordStatus), name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str | None] = mapped_column(String(60))
    price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    prices_include_tax: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Ids of the property's taxes that apply to this item.
    tax_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecordStatus.ACTIVE)


class PosOrder(Base):
    """A settled sale. Never edited; corrections go through the invoice (credit note)."""

    __tablename__ = "pos_orders"
    __table_args__ = (
        _property_fk("pos_orders"),
        ForeignKeyConstraint(
            ["outlet_id", "property_id"],
            ["pos_outlets.id", "pos_outlets.property_id"],
            name="fk_pos_orders_outlet_same_property",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "idempotency_key", name="uq_pos_orders_idempotency"),
        CheckConstraint(enum_check("settlement", Settlement), name="settlement"),
        CheckConstraint(
            "(settlement = 'room') = (reservation_id IS NOT NULL)"
            " AND (settlement = 'paid') = (payment_id IS NOT NULL)",
            name="settlement_links",
        ),
        CheckConstraint("total > 0", name="total"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    outlet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    settlement: Mapped[str] = mapped_column(String(10), nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reservations.id", ondelete="RESTRICT"), index=True
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PosOrderItem(Base):
    """One line of a sale, as sold (name and price copied from the catalogue)."""

    __tablename__ = "pos_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity"),
        CheckConstraint("total > 0", name="total"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pos_orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
