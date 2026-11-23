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
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import BlockStatus, RoomBlock
from app.modules.properties.models import Property, RecordStatus
from app.modules.rates import pricing
from app.modules.rates.service import price_stay
from app.modules.reservations.models import (
    Reservation,
    ReservationRoom,
    ReservationStatus,
    ReservationStatusChange,
)
from app.modules.rooms.models import HousekeepingStatus, MaintenanceStatus, Room, RoomType

REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I


class BookingError(ValueError):
    """The booking cannot be made; the message is shown to staff. ``status`` is the HTTP
    status the API should use."""

    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


def new_reference() -> str:
    return "LOS-" + "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(6))


async def room_is_blocked(
    db: AsyncSession, room_id: uuid.UUID, check_in: date, check_out: date
) -> bool:
    return bool(
        await db.scalar(
            select(func.count())
            .select_from(RoomBlock)
            .where(
                RoomBlock.room_id == room_id,
                RoomBlock.status == BlockStatus.ACTIVE,
                RoomBlock.start_date < check_out,
                RoomBlock.end_date > check_in,
            )
        )
    )


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
    db: AsyncSession,
    room_type_id: uuid.UUID,
    check_in: date,
    check_out: date,
    exclude_reservation_id: uuid.UUID | None = None,
) -> list[NightAvailability]:
    """Free rooms per night. ``exclude_reservation_id`` leaves a booking's own rooms out of
    the count, for changing that booking's dates."""
    sellable = await sellable_rooms(db, room_type_id)
    rows = await db.execute(
        text(
            """
            SELECT d::date AS night,
                   (SELECT count(*) FROM room_blocks b JOIN rooms r ON r.id = b.room_id
                     WHERE r.room_type_id = :rt AND r.status = 'active'
                       AND r.maintenance_status <> 'out_of_order'
                       AND b.status = 'active'
                       AND b.start_date <= d::date AND b.end_date > d::date) AS blocked,
                   (SELECT count(*) FROM reservation_rooms rr
                     WHERE rr.room_type_id = :rt
                       AND rr.status IN ('provisional', 'confirmed', 'checked_in')
                       AND rr.check_in <= d::date AND rr.check_out > d::date
                       AND (CAST(:excl AS uuid) IS NULL OR rr.reservation_id <> CAST(:excl AS uuid))
                   ) AS booked
            FROM generate_series(CAST(:ci AS date), CAST(:co AS date) - 1, interval '1 day') d
            ORDER BY night
            """
        ),
        {"rt": room_type_id, "ci": check_in, "co": check_out, "excl": exclude_reservation_id},
    )
    # Dated blocks remove a room from sale only on their nights.
    return [NightAvailability(r.night, sellable - int(r.blocked), int(r.booked)) for r in rows]


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
    user_id: uuid.UUID | None,
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
        if await room_is_blocked(db, room.id, check_in, check_out):
            raise BookingError(
                f"Room {room.number} is blocked for maintenance on some of these nights."
            )

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
    ReservationStatus.PROVISIONAL: {
        ReservationStatus.CONFIRMED,
        ReservationStatus.CANCELLED,
        ReservationStatus.NO_SHOW,
    },
    ReservationStatus.CONFIRMED: {
        ReservationStatus.CHECKED_IN,
        ReservationStatus.CANCELLED,
        ReservationStatus.NO_SHOW,
    },
    ReservationStatus.CHECKED_IN: {ReservationStatus.CHECKED_OUT},
}


async def change_status(
    db: AsyncSession,
    reservation: Reservation,
    to: ReservationStatus,
    *,
    user_id: uuid.UUID | None,
    reason: str | None = None,
    today: date | None = None,
) -> None:
    """Move a booking through its life: confirm, check in, check out, cancel, no-show.

    ``today`` is the property's local date; check-in and no-show depend on it.
    """
    if to not in ALLOWED_TRANSITIONS.get(reservation.status, set()):
        current = reservation.status.replace("_", " ")
        raise BookingError(f"A {current} booking cannot become {to.replace('_', ' ')}.")
    if to == ReservationStatus.CANCELLED and not reason:
        raise BookingError("Give a reason for the cancellation.", 422)
    rooms = (
        await db.scalars(
            select(ReservationRoom).where(ReservationRoom.reservation_id == reservation.id)
        )
    ).all()
    if to == ReservationStatus.CHECKED_IN:
        assert today is not None
        if today < reservation.check_in:
            raise BookingError(f"Check-in opens on {reservation.check_in.isoformat()}.")
        if today >= reservation.check_out:
            raise BookingError("The stay has already ended. Mark it as a no-show instead.")
        for rr in rooms:
            if rr.room_id is None:
                raise BookingError("Assign a room to every booked room before check-in.")
            room = await db.get(Room, rr.room_id)
            assert room is not None
            if room.maintenance_status == MaintenanceStatus.OUT_OF_ORDER:
                raise BookingError(f"Room {room.number} is out of order. Move the guest first.")
    if to == ReservationStatus.NO_SHOW:
        assert today is not None
        if today < reservation.check_in:
            raise BookingError("A booking can only be marked as a no-show from its arrival day.")
    previous = reservation.status
    reservation.status = to
    reservation.cancellation_reason = reason if to == ReservationStatus.CANCELLED else None
    for rr in rooms:
        rr.status = to
        if to == ReservationStatus.CHECKED_OUT and rr.room_id is not None:
            # Hand-off to housekeeping: the room needs cleaning before the next guest.
            room = await db.get(Room, rr.room_id)
            assert room is not None
            room.housekeeping_status = HousekeepingStatus.DIRTY
            room.housekeeping_updated_at = datetime.now(UTC)
            room.housekeeping_updated_by = user_id
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


ASSIGNABLE = (
    ReservationStatus.PROVISIONAL,
    ReservationStatus.CONFIRMED,
    ReservationStatus.CHECKED_IN,
)


async def free_rooms(db: AsyncSession, rr: ReservationRoom) -> list[Room]:
    """Rooms of the booked type with no other active stay overlapping this one."""
    clash = (
        select(ReservationRoom.room_id)
        .where(
            ReservationRoom.room_id.is_not(None),
            ReservationRoom.id != rr.id,
            ReservationRoom.status.in_(ASSIGNABLE),
            ReservationRoom.check_in < rr.check_out,
            ReservationRoom.check_out > rr.check_in,
        )
        .scalar_subquery()
    )
    blocked = (
        select(RoomBlock.room_id)
        .where(
            RoomBlock.status == BlockStatus.ACTIVE,
            RoomBlock.start_date < rr.check_out,
            RoomBlock.end_date > rr.check_in,
        )
        .scalar_subquery()
    )
    rows = await db.scalars(
        select(Room)
        .where(
            Room.room_type_id == rr.room_type_id,
            Room.status == RecordStatus.ACTIVE,
            Room.maintenance_status != MaintenanceStatus.OUT_OF_ORDER,
            Room.id.not_in(clash),
            Room.id.not_in(blocked),
        )
        .order_by(func.length(Room.number), Room.number)
    )
    return list(rows.all())


async def assign_room(db: AsyncSession, rr: ReservationRoom, room_id: uuid.UUID | None) -> None:
    """Allocate, move or unassign a physical room. Moves stay within the booked room type,
    so inventory and price are unchanged; the exclusion constraint is the final guard."""
    if rr.status not in ASSIGNABLE:
        raise BookingError("Rooms can only be assigned to active bookings.")
    if room_id is not None:
        room = await db.get(Room, room_id)
        if room is None or room.property_id != rr.property_id:
            raise BookingError("Choose a room of this property.", 422)
        if room.room_type_id != rr.room_type_id:
            raise BookingError("Choose a room of the booked room type.", 422)
        if room.status != RecordStatus.ACTIVE:
            raise BookingError(f"Room {room.number} is archived.", 422)
        if room.maintenance_status == MaintenanceStatus.OUT_OF_ORDER:
            raise BookingError(f"Room {room.number} is out of order.")
        if await room_is_blocked(db, room.id, rr.check_in, rr.check_out):
            raise BookingError(
                f"Room {room.number} is blocked for maintenance on some of these nights."
            )
    rr.room_id = room_id
    await db.flush()


CHANGEABLE = (ReservationStatus.PROVISIONAL, ReservationStatus.CONFIRMED)


async def change_dates(
    db: AsyncSession,
    *,
    prop: Property,
    reservation: Reservation,
    check_in: date,
    check_out: date,
    user_id: uuid.UUID | None,
) -> tuple[Decimal, Decimal]:
    """Move a booking to new dates. Goes through the same lock-and-count as a new booking,
    not counting the booking's own rooms, and re-prices every room at today's rates.
    Assigned rooms stay assigned; if one is taken on the new dates the exclusion constraint
    refuses the change. Returns (old total, new total)."""
    if reservation.status not in CHANGEABLE:
        raise BookingError("Only provisional or confirmed bookings can change dates.")
    if check_out <= check_in:
        raise BookingError("Check-out must be after check-in.", 422)
    rooms = (
        await db.scalars(
            select(ReservationRoom).where(ReservationRoom.reservation_id == reservation.id)
        )
    ).all()
    type_ids = sorted({rr.room_type_id for rr in rooms})
    locked = (
        await db.scalars(
            select(RoomType)
            .where(RoomType.id.in_(type_ids))
            .order_by(RoomType.id)
            .with_for_update()
        )
    ).all()
    names = {rt.id: rt.name for rt in locked}

    priced = []
    for rr in rooms:
        try:
            priced.append(
                await price_stay(
                    db,
                    prop,
                    rate_plan_id=rr.rate_plan_id,
                    room_type_id=rr.room_type_id,
                    check_in=check_in,
                    check_out=check_out,
                    adults=rr.adults,
                    children=rr.children,
                )
            )
        except pricing.QuoteError as exc:
            raise BookingError(f"{names[rr.room_type_id]}: {exc}", 422) from None

    wanted = Counter(rr.room_type_id for rr in rooms)
    for type_id, count in wanted.items():
        for night in await availability(db, type_id, check_in, check_out, reservation.id):
            if night.free < count:
                free = night.free
                raise BookingError(
                    f"Only {free} {names[type_id]} {'room is' if free == 1 else 'rooms are'} "
                    f"free on {night.night.isoformat()}."
                )

    old_total = reservation.total_amount
    old_dates = f"{reservation.check_in.isoformat()} to {reservation.check_out.isoformat()}"
    for rr, p in zip(rooms, priced, strict=True):
        rr.check_in, rr.check_out = check_in, check_out
        rr.total_amount = p.quote.total
        rr.tax_amount = p.quote.tax_total
        rr.price_snapshot = _snapshot(p.quote, p.plan.name, p.room_type.name)
    reservation.check_in, reservation.check_out = check_in, check_out
    reservation.total_amount = sum((p.quote.total for p in priced), Decimal("0.00"))
    reservation.tax_amount = sum((p.quote.tax_total for p in priced), Decimal("0.00"))
    db.add(
        ReservationStatusChange(
            organisation_id=reservation.organisation_id,
            property_id=reservation.property_id,
            reservation_id=reservation.id,
            from_status=reservation.status,
            to_status=reservation.status,
            reason=(
                f"Dates changed from {old_dates} to {check_in.isoformat()} to "
                f"{check_out.isoformat()}; total {old_total} to {reservation.total_amount}"
            ),
            changed_by=user_id,
        )
    )
    await db.flush()
    return old_total, reservation.total_amount
