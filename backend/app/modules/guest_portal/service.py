"""Creating and resolving guest links (ADR-0013)."""

import uuid
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import set_tenant_context
from app.core.security import hash_token, new_token
from app.modules.guest_portal.models import GuestAccessToken
from app.modules.reservations.models import Reservation

VALID_AFTER_CHECKOUT = timedelta(days=30)


def link_for(token: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/stay/{token}"


async def create_link(
    db: AsyncSession, reservation: Reservation, *, user_id: uuid.UUID | None
) -> tuple[str, datetime]:
    """A new secret link for the booking. The token itself is returned once, never stored."""
    token = new_token()
    expires = datetime.combine(reservation.check_out + VALID_AFTER_CHECKOUT, time(23, 59), UTC)
    db.add(
        GuestAccessToken(
            organisation_id=reservation.organisation_id,
            property_id=reservation.property_id,
            reservation_id=reservation.id,
            token_hash=hash_token(token),
            created_at=datetime.now(UTC),
            expires_at=expires,
            created_by=user_id,
        )
    )
    await db.flush()
    return link_for(token), expires


async def revoke_all(db: AsyncSession, reservation: Reservation) -> int:
    result = await db.execute(
        update(GuestAccessToken)
        .where(
            GuestAccessToken.reservation_id == reservation.id,
            GuestAccessToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def resolve(db: AsyncSession, token: str) -> uuid.UUID | None:
    """The reservation a valid token opens, with the RLS context set to its organisation."""
    if not 20 <= len(token) <= 100:
        return None
    row = (
        await db.execute(
            text("SELECT organisation_id, reservation_id FROM guest_portal_access(:h)"),
            {"h": hash_token(token)},
        )
    ).first()
    if row is None:
        return None
    await set_tenant_context(db, user_id=None, organisation_id=row.organisation_id)
    return uuid.UUID(str(row.reservation_id))
