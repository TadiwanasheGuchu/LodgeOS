"""Email delivery adapters (ADR-0011). Providers send one rendered message and return the
provider's message id, or raise ``DeliveryError``."""

import asyncio
import json
import smtplib
import ssl
import uuid
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Protocol

import structlog

from app.core.config import Settings, get_settings
from app.core.redis import get_redis

log = structlog.get_logger()
MOCK_MAILBOX = "mock-mailbox"


class DeliveryError(Exception):
    """Sending failed; the worker retries later."""


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    from_address: str
    from_name: str
    reply_to: str | None
    subject: str
    text: str
    html: str


class EmailProvider(Protocol):
    name: str

    async def send(self, message: OutgoingEmail) -> str: ...


def build_mime(message: OutgoingEmail, domain: str) -> EmailMessage:
    mime = EmailMessage()
    mime["From"] = formataddr((message.from_name, message.from_address))
    mime["To"] = message.to
    if message.reply_to:
        mime["Reply-To"] = message.reply_to
    mime["Subject"] = message.subject
    mime["Message-ID"] = make_msgid(domain=domain)
    mime.set_content(message.text)
    mime.add_alternative(message.html, subtype="html")
    return mime


class MockProvider:
    """Sends nothing. Keeps the last 200 messages in Redis for development and tests."""

    name = "mock"

    async def send(self, message: OutgoingEmail) -> str:
        message_id = f"mock-{uuid.uuid4()}"
        redis = get_redis()
        await redis.lpush(MOCK_MAILBOX, json.dumps({"id": message_id, **asdict(message)}))
        await redis.ltrim(MOCK_MAILBOX, 0, 199)
        log.info("email.mock_delivered", to=message.to, subject=message.subject, id=message_id)
        return message_id


class SmtpProvider:
    """Standard SMTP relay; works with any provider that offers SMTP submission."""

    name = "smtp"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _send_sync(self, message: OutgoingEmail) -> str:
        s = self.settings
        domain = message.from_address.rsplit("@", 1)[-1]
        mime = build_mime(message, domain)
        context = ssl.create_default_context()
        try:
            if s.smtp_security == "tls":
                client: smtplib.SMTP = smtplib.SMTP_SSL(
                    s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds, context=context
                )
            else:
                client = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds)
            with client:
                client.ehlo()
                if s.smtp_security == "starttls":
                    client.starttls(context=context)
                    client.ehlo()
                if s.smtp_username and s.smtp_password:
                    client.login(s.smtp_username, s.smtp_password.get_secret_value())
                refused = client.send_message(mime)
        except (smtplib.SMTPException, OSError) as exc:
            raise DeliveryError(f"{type(exc).__name__}: {exc}"[:500]) from exc
        if refused:
            raise DeliveryError(f"Recipient refused: {refused}"[:500])
        return str(mime["Message-ID"])

    async def send(self, message: OutgoingEmail) -> str:
        return await asyncio.to_thread(self._send_sync, message)


def get_provider(settings: Settings | None = None) -> EmailProvider:
    settings = settings or get_settings()
    if settings.email_provider == "smtp":
        return SmtpProvider(settings)
    if settings.environment == "production":
        raise RuntimeError("Production needs LODGEOS_EMAIL_PROVIDER=smtp; the mock sends nothing.")
    return MockProvider()
