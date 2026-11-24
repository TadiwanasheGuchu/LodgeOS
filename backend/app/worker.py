"""The background worker: email delivery and expiry of website booking holds."""

import asyncio

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.booking_engine.service import expire_holds
from app.modules.notifications import service as notifications
from app.modules.notifications.providers import EmailProvider

log = structlog.get_logger()


async def run_once(
    sessionmaker: async_sessionmaker[AsyncSession], provider: EmailProvider
) -> tuple[int, int]:
    expired = await expire_holds(sessionmaker)
    sent = await notifications.deliver_due(sessionmaker, provider)
    return expired, sent


async def run_forever(
    sessionmaker: async_sessionmaker[AsyncSession],
    provider: EmailProvider,
    interval_seconds: float = 5.0,
) -> None:
    log.info("worker.started", provider=provider.name)
    while True:
        try:
            await run_once(sessionmaker, provider)
        except Exception:
            log.exception("worker.error")
        await asyncio.sleep(interval_seconds)
