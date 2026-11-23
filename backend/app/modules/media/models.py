"""Photos and logos (ADR-0014)."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, new_uuid
from app.core.types import enum_check


class MediaKind(enum.StrEnum):
    LOGO = "logo"
    PROPERTY_PHOTO = "property_photo"
    ROOM_TYPE_PHOTO = "room_type_photo"


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["property_id", "organisation_id"],
            ["properties.id", "properties.organisation_id"],
            name="fk_media_assets_property_same_org",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["room_type_id", "property_id"],
            ["room_types.id", "room_types.property_id"],
            name="fk_media_assets_room_type_same_property",
            ondelete="RESTRICT",
        ),
        CheckConstraint(enum_check("kind", MediaKind), name="kind"),
        CheckConstraint(
            "(kind = 'room_type_photo') = (room_type_id IS NOT NULL)", name="room_type"
        ),
        CheckConstraint("kind = 'logo' OR alt_text IS NOT NULL", name="alt_text"),
        Index(
            "ix_media_assets_live",
            "property_id",
            "kind",
            "sort_order",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    room_type_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # {"sm": {"width": 400, "height": 267, "bytes": 18234}, ...}
    variants: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    storage: Mapped[str] = mapped_column(String(10), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
