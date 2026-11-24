"""Background work for the booking engine (ADR-0012)."""

import uuid

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import set_tenant_context
from app.modules.audit import service as audit
from app.modules.properties.models import Property
from app.modules.reservations import service as bookings
from app.modules.reservations.models import Reservation, ReservationStatus

log = structlog.get_logger()


async def expire_holds(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Cancel website requests whose hold has passed, freeing the rooms."""
    async with sessionmaker() as db, db.begin():
        due = (
            await db.execute(
                text("SELECT organisation_id, reservation_id FROM expired_request_holds()")
            )
        ).all()
    cancelled = 0
    for org_id, reservation_id in due:
        if await _expire_one(sessionmaker, org_id, reservation_id):
            cancelled += 1
    return cancelled


async def _expire_one(
    sessionmaker: async_sessionmaker[AsyncSession],
    org_id: uuid.UUID,
    reservation_id: uuid.UUID,
) -> bool:
    async with sessionmaker() as db, db.begin():
        await set_tenant_context(db, user_id=None, organisation_id=org_id)
        r = await db.scalar(
            select(Reservation).where(Reservation.id == reservation_id).with_for_update()
        )
        # Staff may have confirmed or cancelled it since the list was read.
        if r is None or r.status != ReservationStatus.PROVISIONAL or r.hold_expires_at is None:
            return False
        prop = await db.get(Property, r.property_id)
        assert prop is not None
        reason = f"Request not confirmed within {prop.request_hold_hours} hours."
        await bookings.change_status(
            db, r, ReservationStatus.CANCELLED, user_id=None, reason=reason
        )
        await audit.record(
            db,
            action="reservation.cancelled",
            organisation_id=org_id,
            actor_user_id=None,
            entity_type="reservation",
            entity_id=r.id,
            data={"reference": r.reference, "reason": reason, "via": "hold_expiry"},
        )
        log.info("booking.hold_expired", reference=r.reference)
        return True
