"""Reservation engine: availability and booking, safe under concurrent requests.

How double booking is prevented
1. Room-type inventory: every booking first locks the room-type rows it needs
   (``SELECT ... FOR UPDATE``, in id order to avoid deadlocks). Concurrent bookings for the
   same room type therefore run one after another, and each counts free rooms per night
   after the previous one committed.
2. Physical rooms: an exclusion constraint on ``reservation_rooms`` rejects two active
   stays in one room on the same night, whatever the application does.
Caches never decide availability.
"""

import secrets
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.properties.models import Property, RecordStatus
from app.modules.rates import pricing
from app.modules.rates.service import price_stay
from app.modules.reservations.models import (
    Reservation,
    ReservationRoom,
    ReservationStatus,
    ReservationStatusChange,
)
from app.modules.rooms.models import MaintenanceStatus, Room, RoomType

REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I


class BookingError(ValueError):
    """The booking cannot be made; the message is shown to staff. ``status`` is the HTTP
    status the API should use."""

    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


def new_reference() -> str:
    return "LOS-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


def nights(check_in: date, check_out: date) -> list[date]:
    return [check_in + timedelta(days=i) for i in range((check_out - check_in).days)]


@dataclass(frozen=True)
class NightAvailability:
    night: date
    sellable: int
    booked: int

    @property
    def free(self) -> int:
        return max(0, self.sellable - self.booked)


async def sellable_rooms(db: AsyncSession, room_type_id: uuid.UUID) -> int:
    """Active rooms of the type that are not out of order. (Out of order is not dated yet;
    dated room blocks arrive with the maintenance module.)"""
    return int(
        await db.scalar(
            select(func.count())
            .select_from(Room)
            .where(
                Room.room_type_id == room_type_id,
                Room.status == RecordStatus.ACTIVE,
                Room.maintenance_status != MaintenanceStatus.OUT_OF_ORDER,
            )
        )
        or 0
    )


async def availability(
    db: AsyncSession, room_type_id: uuid.UUID, check_in: date, check_out: date
) -> list[NightAvailability]:
    sellable = await sellable_rooms(db, room_type_id)
    rows = await db.execute(
        text(
            """
            SELECT d::date AS night,
                   (SELECT count(*) FROM reservation_rooms rr
                     WHERE rr.room_type_id = :rt
                       AND rr.status IN ('provisional', 'confirmed', 'checked_in')
                       AND rr.check_in <= d::date AND rr.check_out > d::date) AS booked
            FROM generate_series(CAST(:ci AS date), CAST(:co AS date) - 1, interval '1 day') d
            ORDER BY night
            """
        ),
        {"rt": room_type_id, "ci": check_in, "co": check_out},
    )
    return [NightAvailability(r.night, sellable, int(r.booked)) for r in rows]


@dataclass(frozen=True)
class RoomRequest:
    room_type_id: uuid.UUID
    rate_plan_id: uuid.UUID
    adults: int
    children: int
    room_id: uuid.UUID | None = None


def _snapshot(q: pricing.Quote, plan_name: str, room_type_name: str) -> dict[str, Any]:
    """The price breakdown as sold, stored with the booking (amounts as strings)."""

    def s(v: Decimal) -> str:
        return str(v)

    return {
        "currency": q.currency,
        "rate_plan": plan_name,
        "room_type": room_type_name,
        "prices_include_tax": q.prices_include_tax,
        "nights": [
            {
                "date": n.date.isoformat(),
                "season": n.season,
                "weekend": n.weekend,
                "room_price": s(n.room_price),
                "extra_adults": n.extra_adults,
                "extra_adult_amount": s(n.extra_adult_amount),
                "extra_children": n.extra_children,
                "extra_child_amount": s(n.extra_child_amount),
                "amount": s(n.amount),
            }
            for n in q.nights
        ],
        "net_total": s(q.net_total),
        "taxes": [
            {"name": t.name, "rate_percent": s(t.rate_percent), "amount": s(t.amount)}
            for t in q.taxes
        ],
        "tax_total": s(q.tax_total),
        "total": s(q.total),
    }


async def create_reservation(
    db: AsyncSession,
    *,
    prop: Property,
    guest_id: uuid.UUID,
    check_in: date,
    check_out: date,
    rooms: list[RoomRequest],
    status: ReservationStatus,
    source: str,
    notes: str | None,
    user_id: uuid.UUID,
) -> Reservation:
    if not rooms:
        raise BookingError("Add at least one room.", 422)
    if status not in (ReservationStatus.PROVISIONAL, ReservationStatus.CONFIRMED):
        raise BookingError("New bookings are provisional or confirmed.", 422)

    # 1. Serialise bookings per room type: lock the room types needed, in a fixed order.
    type_ids = sorted({r.room_type_id for r in rooms})
    locked = (
        await db.scalars(
            select(RoomType)
            .where(RoomType.id.in_(type_ids), RoomType.property_id == prop.id)
            .order_by(RoomType.id)
            .with_for_update()
        )
    ).all()
    if len(locked) != len(type_ids):
        raise BookingError("Choose room types from this property.", 422)
    names = {rt.id: rt.name for rt in locked}

    # 2. Price every room with the same engine as the calculator.
    priced = []
    for r in rooms:
        try:
            priced.append(
                await price_stay(
                    db,
                    prop,
                    rate_plan_id=r.rate_plan_id,
                    room_type_id=r.room_type_id,
                    check_in=check_in,
                    check_out=check_out,
                    adults=r.adults,
                    children=r.children,
                )
            )
        except pricing.QuoteError as exc:
            raise BookingError(f"{names[r.room_type_id]}: {exc}", 422) from None
    currencies = {p.quote.currency for p in priced}
    if len(currencies) != 1:
        raise BookingError("All rooms on one booking must use the same currency.", 422)

    # 3. Room-type inventory for every night, now that competing bookings are queued.
    wanted = Counter(r.room_type_id for r in rooms)
    for type_id, count in wanted.items():
        for night in await availability(db, type_id, check_in, check_out):
            if night.free < count:
                free = night.free
                raise BookingError(
                    f"Only {free} {names[type_id]} {'room is' if free == 1 else 'rooms are'} "
                    f"free on {night.night.isoformat()}."
                )

    # 4. Physical rooms, if chosen now: must be of the booked type and usable.
    for r in rooms:
        if r.room_id is None:
            continue
        room = await db.get(Room, r.room_id)
        if room is None or room.property_id != prop.id or room.room_type_id != r.room_type_id:
            raise BookingError("Choose a room of the booked room type.", 422)
        if room.status != RecordStatus.ACTIVE:
            raise BookingError(f"Room {room.number} is archived.", 422)
        if room.maintenance_status == MaintenanceStatus.OUT_OF_ORDER:
            raise BookingError(f"Room {room.number} is out of order.")

    # 5. Write the booking.
    reference = new_reference()
    while await db.scalar(select(Reservation.id).where(Reservation.reference == reference)):
        reference = new_reference()
    reservation = Reservation(
        organisation_id=prop.organisation_id,
        property_id=prop.id,
        reference=reference,
        status=status,
        source=source,
        guest_id=guest_id,
        check_in=check_in,
        check_out=check_out,
        currency=currencies.pop(),
        total_amount=sum((p.quote.total for p in priced), Decimal("0.00")),
        tax_amount=sum((p.quote.tax_total for p in priced), Decimal("0.00")),
        notes=notes,
        created_by=user_id,
    )
    db.add(reservation)
    await db.flush()
    for r, p in zip(rooms, priced, strict=True):
        db.add(
            ReservationRoom(
                organisation_id=prop.organisation_id,
                property_id=prop.id,
                reservation_id=reservation.id,
                room_type_id=r.room_type_id,
                room_id=r.room_id,
                rate_plan_id=r.rate_plan_id,
                check_in=check_in,
                check_out=check_out,
                status=status,
                adults=r.adults,
                children=r.children,
                total_amount=p.quote.total,
                tax_amount=p.quote.tax_total,
                price_snapshot=_snapshot(p.quote, p.plan.name, p.room_type.name),
            )
        )
    db.add(
        ReservationStatusChange(
            organisation_id=prop.organisation_id,
            property_id=prop.id,
            reservation_id=reservation.id,
            from_status=None,
            to_status=status,
            changed_by=user_id,
        )
    )
    await db.flush()
    return reservation


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ReservationStatus.PROVISIONAL: {ReservationStatus.CONFIRMED, ReservationStatus.CANCELLED},
    ReservationStatus.CONFIRMED: {ReservationStatus.CANCELLED, ReservationStatus.NO_SHOW},
}


async def change_status(
    db: AsyncSession,
    reservation: Reservation,
    to: ReservationStatus,
    *,
    user_id: uuid.UUID,
    reason: str | None = None,
) -> None:
    """Confirm, cancel or mark as no-show. Check-in and check-out arrive in Phase 2.3."""
    if to not in ALLOWED_TRANSITIONS.get(reservation.status, set()):
        current = reservation.status.replace("_", " ")
        raise BookingError(f"A {current} booking cannot become {to.replace('_', ' ')}.")
    if to == ReservationStatus.CANCELLED and not reason:
        raise BookingError("Give a reason for the cancellation.", 422)
    previous = reservation.status
    reservation.status = to
    reservation.cancellation_reason = reason if to == ReservationStatus.CANCELLED else None
    rooms = (
        await db.scalars(
            select(ReservationRoom).where(ReservationRoom.reservation_id == reservation.id)
        )
    ).all()
    for room in rooms:
        room.status = to
    db.add(
        ReservationStatusChange(
            organisation_id=reservation.organisation_id,
            property_id=reservation.property_id,
            reservation_id=reservation.id,
            from_status=previous,
            to_status=to,
            reason=reason,
            changed_by=user_id,
        )
    )
    await db.flush()


def overlaps(check_in: date, check_out: date) -> ColumnElement[bool]:
    """Filter for reservations whose stay overlaps [check_in, check_out)."""
    return and_(Reservation.check_in < check_out, Reservation.check_out > check_in)
