import enum
import uuid
from datetime import time

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid
from app.core.types import enum_check


class PropertyType(enum.StrEnum):
    GUESTHOUSE = "guesthouse"
    BOUTIQUE_HOTEL = "boutique_hotel"
    HOTEL = "hotel"
    LODGE = "lodge"
    SAFARI_LODGE = "safari_lodge"
    RESORT = "resort"
    SERVICED_APARTMENTS = "serviced_apartments"
    OTHER = "other"


class RecordStatus(enum.StrEnum):
    """Setup records are archived, never deleted, so history keeps its references."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class Property(TimestampMixin, Base):
    """One hospitality site. Timezone and currency are the property's own; they start
    from the organisation defaults but may differ (e.g. a group with lodges in Namibia
    and Zimbabwe)."""

    __tablename__ = "properties"
    __table_args__ = (
        UniqueConstraint("organisation_id", "slug"),
        # Lets child tables prove, with a foreign key, that they belong to the same tenant.
        UniqueConstraint("id", "organisation_id", name="uq_properties_id_org"),
        CheckConstraint(enum_check("property_type", PropertyType), name="property_type"),
        CheckConstraint(enum_check("status", RecordStatus), name="status"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso4217"),
        CheckConstraint("country_code IS NULL OR country_code ~ '^[A-Z]{2}$'", name="country"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_format"),
        CheckConstraint(
            "weekend_nights <@ ARRAY[1,2,3,4,5,6,7]::smallint[]", name="weekend_nights"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    property_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecordStatus.ACTIVE)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2))
    address_line1: Mapped[str | None] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    # Printed on invoices (ADR-0009). "Tax invoice" is shown only when a tax number is set.
    legal_name: Mapped[str | None] = mapped_column(String(200))
    tax_number: Mapped[str | None] = mapped_column(String(50))
    # Local times at the property. Stored as wall-clock time, interpreted in `timezone`.
    check_in_time: Mapped[time] = mapped_column(Time, nullable=False)
    check_out_time: Mapped[time] = mapped_column(Time, nullable=False)
    # Nights that use weekend prices, as ISO weekdays of the night's date (1 = Monday ...
    # 7 = Sunday). The default, Friday and Saturday nights, suits most leisure properties.
    weekend_nights: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), nullable=False, server_default="{5,6}"
    )


class Building(TimestampMixin, Base):
    """A block, wing or separate structure within a property (optional for small sites)."""

    __tablename__ = "buildings"
    __table_args__ = (
        UniqueConstraint("property_id", "name"),
        UniqueConstraint("id", "property_id", name="uq_buildings_id_property"),
        ForeignKeyConstraint(
            ["property_id", "organisation_id"],
            ["properties.id", "properties.organisation_id"],
            name="fk_buildings_property_same_org",
            ondelete="RESTRICT",
        ),
        CheckConstraint(enum_check("status", RecordStatus), name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecordStatus.ACTIVE)
