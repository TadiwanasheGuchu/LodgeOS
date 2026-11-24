"""Outbox of messages to guests (ADR-0011). Rows are written with the request that asks for
them and delivered by the worker; the rendered content is kept as sent."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, new_uuid
from app.core.types import enum_check


class NotificationStatus(enum.StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class NotificationKind(enum.StrEnum):
    BOOKING_CONFIRMATION = "booking_confirmation"
    INVOICE = "invoice"
    RECEIPT = "receipt"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["property_id", "organisation_id"],
            ["properties.id", "properties.organisation_id"],
            name="fk_notifications_property_same_org",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organisation_id", "idempotency_key", name="uq_notifications_idempotency"),
        CheckConstraint(enum_check("status", NotificationStatus), name="status"),
        CheckConstraint(enum_check("kind", NotificationKind), name="kind"),
        CheckConstraint("channel = 'email'", name="channel"),
        CheckConstraint("(status = 'sent') = (sent_at IS NOT NULL)", name="sent_at"),
        Index(
            "ix_notifications_due",
            "next_attempt_at",
            postgresql_where=text("status = 'queued'"),
        ),
        Index("ix_notifications_subject", "subject_type", "subject_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    # What the message is about: reservation, invoice or payment.
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(200), nullable=False)
    reply_to: Mapped[str | None] = mapped_column(String(320))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=NotificationStatus.QUEUED
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1000))
    provider: Mapped[str | None] = mapped_column(String(40))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # Empty for messages the system queues itself, e.g. after a website booking.
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
