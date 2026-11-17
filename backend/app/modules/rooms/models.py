import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid
from app.core.types import enum_check
from app.modules.properties.models import RecordStatus


class HousekeepingStatus(enum.StrEnum):
    """Cleanliness only. Says nothing about whether the room is occupied or sellable."""

    DIRTY = "dirty"
    CLEAN = "clean"
    INSPECTED = "inspected"


class MaintenanceStatus(enum.StrEnum):
    """
    NONE: no maintenance issue.
    OUT_OF_SERVICE: a minor issue; the room stays in inventory but should not be assigned
        until resolved (e.g. a broken kettle).
    OUT_OF_ORDER: the room is removed from sellable inventory (e.g. a burst pipe).
    """

    NONE = "none"
    OUT_OF_SERVICE = "out_of_service"
    OUT_OF_ORDER = "out_of_order"


class RoomType(TimestampMixin, Base):
    """What guests book: a category of room with an occupancy limit."""

    __tablename__ = "room_types"
    __table_args__ = (
        UniqueConstraint("property_id", "code"),
        UniqueConstraint("property_id", "name"),
        UniqueConstraint("id", "property_id", name="uq_room_types_id_property"),
        ForeignKeyConstraint(
            ["property_id", "organisation_id"],
            ["properties.id", "properties.organisation_id"],
            name="fk_room_types_property_same_org",
            ondelete="RESTRICT",
        ),
        CheckConstraint(enum_check("status", RecordStatus), name="status"),
        CheckConstraint("code ~ '^[A-Z0-9][A-Z0-9-]{0,9}$'", name="code_format"),
        CheckConstraint("base_occupancy >= 1", name="base_occupancy_positive"),
        CheckConstraint("max_occupancy >= base_occupancy", name="max_ge_base"),
        CheckConstraint("max_adults >= 1 AND max_adults <= max_occupancy", name="max_adults"),
        CheckConstraint("max_children >= 0 AND max_children <= max_occupancy", name="max_children"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    bed_configuration: Mapped[str | None] = mapped_column(String(200))
    # Guests included in the base rate; extra-guest charges (Phase 1.4) apply above this.
    base_occupancy: Mapped[int] = mapped_column(Integer, nullable=False)
    max_occupancy: Mapped[int] = mapped_column(Integer, nullable=False)
    max_adults: Mapped[int] = mapped_column(Integer, nullable=False)
    max_children: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecordStatus.ACTIVE)


class Room(TimestampMixin, Base):
    """A physical, numbered room. Occupancy is not stored here: it is derived from
    reservations (Phase 2), so it can never drift from the bookings."""

    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("property_id", "number"),
        UniqueConstraint("id", "property_id", name="uq_rooms_id_property"),
        ForeignKeyConstraint(
            ["property_id", "organisation_id"],
            ["properties.id", "properties.organisation_id"],
            name="fk_rooms_property_same_org",
            ondelete="RESTRICT",
        ),
        # The room type and building must belong to the same property as the room.
        ForeignKeyConstraint(
            ["room_type_id", "property_id"],
            ["room_types.id", "room_types.property_id"],
            name="fk_rooms_room_type_same_property",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["building_id", "property_id"],
            ["buildings.id", "buildings.property_id"],
            name="fk_rooms_building_same_property",
            ondelete="RESTRICT",
        ),
        CheckConstraint(enum_check("status", RecordStatus), name="status"),
        CheckConstraint(enum_check("housekeeping_status", HousekeepingStatus), name="hk_status"),
        CheckConstraint(
            enum_check("maintenance_status", MaintenanceStatus), name="maintenance_status"
        ),
        CheckConstraint(
            "(maintenance_status = 'none') = (maintenance_reason IS NULL)",
            name="maintenance_reason_required",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    room_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    building_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    floor: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecordStatus.ACTIVE)
    housekeeping_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=HousekeepingStatus.DIRTY
    )
    housekeeping_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    housekeeping_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    maintenance_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MaintenanceStatus.NONE
    )
    maintenance_reason: Mapped[str | None] = mapped_column(String(500))
    maintenance_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    maintenance_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
