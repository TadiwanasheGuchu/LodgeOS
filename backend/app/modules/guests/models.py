"""Guest records (CRM). Guests belong to an organisation, so a returning guest is
recognised at every property of the group."""

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin, new_uuid


class Guest(TimestampMixin, Base):
    __tablename__ = "guests"
    __table_args__ = (
        Index("ix_guests_org_email", "organisation_id", func.lower(text("email"))),
        Index("ix_guests_org_name", "organisation_id", func.lower(text("last_name"))),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organisations.id", ondelete="RESTRICT"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    country_code: Mapped[str | None] = mapped_column(String(2))
    notes: Mapped[str | None] = mapped_column(Text)
