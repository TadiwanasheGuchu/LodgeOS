"""Rate plans, prices, seasons and taxes.

Money is NUMERIC(12,2) and handled as Decimal; it is never a float. Each rate plan stores
its currency. Tax rates are percentages stored as NUMERIC(7,4) (15% is 15.0000).
"""

import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid
from app.core.types import enum_check
from app.modules.properties.models import RecordStatus

Money = Numeric(12, 2)


class RatePlanKind(enum.StrEnum):
    STANDARD = "standard"
    CORPORATE = "corporate"
    PROMOTIONAL = "promotional"
    PACKAGE = "package"


class MealPlan(enum.StrEnum):
    ROOM_ONLY = "room_only"
    BED_AND_BREAKFAST = "bed_and_breakfast"
    HALF_BOARD = "half_board"
    FULL_BOARD = "full_board"
    ALL_INCLUSIVE = "all_inclusive"


def _property_fk(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["property_id", "organisation_id"],
        ["properties.id", "properties.organisation_id"],
        name=f"fk_{table}_property_same_org",
        ondelete="RESTRICT",
    )


class Tax(TimestampMixin, Base):
    """A tax charged on accommodation at one property (e.g. VAT, tourism levy).

    Nothing about any country's tax is hard-coded; each property configures its own.
    All active taxes are calculated on the net price (not compounded).
    """

    __tablename__ = "taxes"
    __table_args__ = (
        _property_fk("taxes"),
        UniqueConstraint("property_id", "name"),
        CheckConstraint("rate_percent > 0 AND rate_percent < 100", name="rate_range"),
        CheckConstraint(enum_check("status", RecordStatus), name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecordStatus.ACTIVE)


class RatePlan(TimestampMixin, Base):
    __tablename__ = "rate_plans"
    __table_args__ = (
        _property_fk("rate_plans"),
        UniqueConstraint("property_id", "code"),
        UniqueConstraint("property_id", "name"),
        UniqueConstraint("id", "property_id", name="uq_rate_plans_id_property"),
        CheckConstraint(enum_check("kind", RatePlanKind), name="kind"),
        CheckConstraint(enum_check("meal_plan", MealPlan), name="meal_plan"),
        CheckConstraint(enum_check("status", RecordStatus), name="status"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso4217"),
        CheckConstraint("code ~ '^[A-Z0-9][A-Z0-9-]{0,15}$'", name="code_format"),
        CheckConstraint("min_stay_nights >= 1", name="min_stay"),
        CheckConstraint(
            "max_stay_nights IS NULL OR max_stay_nights >= min_stay_nights", name="max_stay"
        ),
        CheckConstraint(
            "stay_from IS NULL OR stay_to IS NULL OR stay_to >= stay_from", name="stay_window"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default=RatePlanKind.STANDARD)
    meal_plan: Mapped[str] = mapped_column(String(24), nullable=False, default=MealPlan.ROOM_ONLY)
    # Copied from the property when the plan is created, and stored so that historical
    # prices keep their currency if the property's currency changes later.
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    prices_include_tax: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_stay_nights: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_stay_nights: Mapped[int | None] = mapped_column(Integer)
    # Optional window of stay dates (for promotions); NULL means always.
    stay_from: Mapped[date | None] = mapped_column(Date)
    stay_to: Mapped[date | None] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecordStatus.ACTIVE)


_PRICE_CHECKS = (
    "base_price >= 0",
    "weekend_price IS NULL OR weekend_price >= 0",
    "extra_adult_price >= 0",
    "extra_child_price >= 0",
)


class RatePlanPrice(TimestampMixin, Base):
    """Nightly prices for one room type under one rate plan, outside any season.

    ``base_price`` covers the room type's base occupancy. ``weekend_price``, when set,
    replaces it on the property's weekend nights. Guests above base occupancy pay the
    extra-adult or extra-child price per night.
    """

    __tablename__ = "rate_plan_prices"
    __table_args__ = (
        UniqueConstraint("rate_plan_id", "room_type_id"),
        ForeignKeyConstraint(
            ["rate_plan_id", "property_id"],
            ["rate_plans.id", "rate_plans.property_id"],
            name="fk_rate_plan_prices_plan_same_property",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["room_type_id", "property_id"],
            ["room_types.id", "room_types.property_id"],
            name="fk_rate_plan_prices_room_type_same_property",
            ondelete="RESTRICT",
        ),
        _property_fk("rate_plan_prices"),
        *(CheckConstraint(c, name=f"price_{i}") for i, c in enumerate(_PRICE_CHECKS)),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rate_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    room_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    weekend_price: Mapped[Decimal | None] = mapped_column(Money)
    extra_adult_price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
    extra_child_price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))


class SeasonalRate(TimestampMixin, Base):
    """Prices that replace the plan's normal prices for one room type on a range of nights
    (``start_date`` to ``end_date``, both inclusive). Seasons for the same plan and room
    type cannot overlap: an exclusion constraint in the database enforces it."""

    __tablename__ = "seasonal_rates"
    __table_args__ = (
        ForeignKeyConstraint(
            ["rate_plan_id", "property_id"],
            ["rate_plans.id", "rate_plans.property_id"],
            name="fk_seasonal_rates_plan_same_property",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["room_type_id", "property_id"],
            ["room_types.id", "room_types.property_id"],
            name="fk_seasonal_rates_room_type_same_property",
            ondelete="RESTRICT",
        ),
        _property_fk("seasonal_rates"),
        CheckConstraint("end_date >= start_date", name="date_order"),
        *(CheckConstraint(c, name=f"price_{i}") for i, c in enumerate(_PRICE_CHECKS)),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rate_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    room_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    weekend_price: Mapped[Decimal | None] = mapped_column(Money)
    extra_adult_price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
    extra_child_price: Mapped[Decimal] = mapped_column(Money, nullable=False, default=Decimal(0))
