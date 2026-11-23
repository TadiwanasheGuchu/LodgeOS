"""Queueing and delivery of notifications (ADR-0011)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.modules.notifications.models import Notification, NotificationStatus
from app.modules.notifications.providers import DeliveryError, EmailProvider, OutgoingEmail
from app.modules.notifications.templates import Rendered, Venue
from app.modules.properties.models import Property

log = structlog.get_logger()

# Delay before attempt n+1 after n failures; after the last, the message is failed.
BACKOFF = [
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=6),
]
MAX_ATTEMPTS = len(BACKOFF) + 1


def venue_of(prop: Property) -> Venue:
    """The property as shown in an email footer."""
    address = [
        line
        for line in (
            prop.address_line1,
            prop.address_line2,
            " ".join(p for p in (prop.postal_code, prop.city) if p) or None,
            prop.region,
        )
        if line
    ]
    return Venue(
        name=prop.name,
        address=address,
        phone=prop.phone,
        email=prop.email,
        legal_name=prop.legal_name,
        tax_number=prop.tax_number,
    )


async def queue(
    db: AsyncSession,
    *,
    prop: Property,
    kind: str,
    subject_type: str,
    subject_id: uuid.UUID,
    recipient: str,
    rendered: Rendered,
    idempotency_key: str,
    user_id: uuid.UUID | None,
) -> tuple[Notification, bool]:
    """Write the message to the outbox in the caller's transaction. A repeated key returns
    the message already queued; the boolean says whether this call created it."""
    now = datetime.now(UTC)
    new_id = await db.scalar(
        insert(Notification)
        .values(
            id=uuid.uuid4(),
            organisation_id=prop.organisation_id,
            property_id=prop.id,
            channel="email",
            kind=kind,
            subject_type=subject_type,
            subject_id=subject_id,
            recipient=recipient,
            sender_name=prop.name,
            reply_to=prop.email,
            title=rendered.subject,
            body_text=rendered.text,
            body_html=rendered.html,
            status=NotificationStatus.QUEUED,
            attempts=0,
            next_attempt_at=now,
            idempotency_key=idempotency_key,
            created_by=user_id,
            created_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_notifications_idempotency")
        .returning(Notification.id)
    )
    row = await db.scalar(
        select(Notification).where(
            Notification.organisation_id == prop.organisation_id,
            Notification.idempotency_key == idempotency_key,
        )
    )
    assert row is not None
    return row, new_id is not None


async def _worker_context(db: AsyncSession) -> None:
    # The one place this setting is used: the worker reads every organisation's outbox.
    await db.execute(text("SELECT set_config('app.notification_worker', 'on', true)"))


async def deliver_one(
    sessionmaker: async_sessionmaker[AsyncSession], provider: EmailProvider
) -> bool:
    """Send the next due message, if any. Returns False when nothing was due."""
    settings = get_settings()
    async with sessionmaker() as db, db.begin():
        await _worker_context(db)
        n = await db.scalar(
            select(Notification)
            .where(
                Notification.status == NotificationStatus.QUEUED,
                Notification.next_attempt_at <= datetime.now(UTC),
            )
            .order_by(Notification.next_attempt_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if n is None:
            return False
        message = OutgoingEmail(
            to=n.recipient,
            from_address=settings.email_from_address,
            from_name=n.sender_name,
            reply_to=n.reply_to,
            subject=n.title,
            text=n.body_text,
            html=n.body_html,
        )
        n.attempts += 1
        n.provider = provider.name
        try:
            n.provider_message_id = await provider.send(message)
        except Exception as exc:
            n.last_error = (str(exc) if isinstance(exc, DeliveryError) else repr(exc))[:1000]
            if n.attempts >= MAX_ATTEMPTS:
                n.status = NotificationStatus.FAILED
                log.warning("notification.failed", id=str(n.id), error=n.last_error)
            else:
                n.next_attempt_at = datetime.now(UTC) + BACKOFF[n.attempts - 1]
                log.info("notification.retry", id=str(n.id), attempt=n.attempts)
            return True
        n.status = NotificationStatus.SENT
        n.sent_at = datetime.now(UTC)
        n.last_error = None
        log.info("notification.sent", id=str(n.id), provider=provider.name)
        return True


async def deliver_due(
    sessionmaker: async_sessionmaker[AsyncSession], provider: EmailProvider, limit: int = 100
) -> int:
    sent = 0
    while sent < limit and await deliver_one(sessionmaker, provider):
        sent += 1
    return sent


async def run_worker(
    sessionmaker: async_sessionmaker[AsyncSession],
    provider: EmailProvider,
    interval_seconds: float = 5.0,
) -> None:
    log.info("notification.worker_started", provider=provider.name)
    while True:
        try:
            await deliver_due(sessionmaker, provider)
        except Exception:
            log.exception("notification.worker_error")
        await asyncio.sleep(interval_seconds)
