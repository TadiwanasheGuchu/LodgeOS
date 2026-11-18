"""Guests, availability and reservations."""

import uuid
from datetime import date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission_anywhere
from app.modules.auth.models import User
from app.modules.auth.permissions import Permission
from app.modules.guests.models import Guest
from app.modules.properties.models import Building, Property, RecordStatus
from app.modules.properties.router import get_property
from app.modules.reservations import service
from app.modules.reservations.models import (
    Reservation,
    ReservationRoom,
    ReservationStatus,
    ReservationStatusChange,
)
from app.modules.reservations.schemas import (
    AssignRoom,
    CalendarOut,
    CalendarRoom,
    CalendarStay,
    DateChange,
    FreeRoom,
    GuestIn,
    GuestOut,
    GuestUpdate,
    NightOut,
    ReservationCreate,
    ReservationDetail,
    ReservationRoomOut,
    ReservationSummary,
    RoomTypeAvailability,
    StatusChange,
    StatusChangeOut,
    TodayOut,
)
from app.modules.rooms.models import Room, RoomType

router = APIRouter(prefix="/api/v1", tags=["reservations"])

CanView = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.RESERVATIONS_VIEW))]
CanManage = Annotated[
    AuthContext, Depends(require_permission_anywhere(Permission.RESERVATIONS_MANAGE))
]

MAX_RANGE_DAYS = 120


def _booking_error(exc: service.BookingError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


# --- guests -----------------------------------------------------------------------------


@router.get("/guests", response_model=list[GuestOut])
async def search_guests(
    auth: CanView,
    db: DB,
    q: Annotated[str, Query(min_length=2, max_length=100)],
) -> list[Guest]:
    """Find returning guests by name, email or phone (organisation-wide)."""
    term = f"%{q.lower()}%"
    rows = await db.scalars(
        select(Guest)
        .where(
            or_(
                func.lower(Guest.first_name + " " + Guest.last_name).like(term),
                func.lower(Guest.email).like(term),
                Guest.phone.like(f"%{q}%"),
            )
        )
        .order_by(Guest.last_name, Guest.first_name)
        .limit(20)
    )
    return list(rows.all())


# --- availability -----------------------------------------------------------------------


@router.get("/properties/{property_id}/availability", response_model=list[RoomTypeAvailability])
async def get_availability(
    property_id: uuid.UUID,
    auth: CanView,
    db: DB,
    check_in: date,
    check_out: date,
) -> list[RoomTypeAvailability]:
    prop = await get_property(db, property_id, auth, Permission.RESERVATIONS_VIEW)
    if check_out <= check_in or (check_out - check_in).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Choose up to 120 nights.")
    types = (
        await db.scalars(
            select(RoomType)
            .where(RoomType.property_id == prop.id, RoomType.status == RecordStatus.ACTIVE)
            .order_by(RoomType.sort_order, RoomType.name)
        )
    ).all()
    out = []
    for rt in types:
        per_night = await service.availability(db, rt.id, check_in, check_out)
        out.append(
            RoomTypeAvailability(
                room_type_id=rt.id,
                room_type_name=rt.name,
                room_type_code=rt.code,
                max_occupancy=rt.max_occupancy,
                free=min(n.free for n in per_night),
                nights=[
                    NightOut(night=n.night, sellable=n.sellable, booked=n.booked, free=n.free)
                    for n in per_night
                ],
            )
        )
    return out


# --- reservations -----------------------------------------------------------------------


async def _summary_rows(db: DB, where: list) -> list[ReservationSummary]:  # type: ignore[type-arg]
    room_counts = (
        select(ReservationRoom.reservation_id, func.count().label("n"))
        .group_by(ReservationRoom.reservation_id)
        .subquery()
    )
    rows = await db.execute(
        select(Reservation, Guest.first_name, Guest.last_name, room_counts.c.n)
        .join(Guest, Guest.id == Reservation.guest_id)
        .join(room_counts, room_counts.c.reservation_id == Reservation.id)
        .where(*where)
        .order_by(Reservation.check_in, Reservation.reference)
    )
    return [
        ReservationSummary(
            id=r.id,
            property_id=r.property_id,
            reference=r.reference,
            status=r.status,
            source=r.source,
            guest_id=r.guest_id,
            guest_name=f"{first} {last}",
            check_in=r.check_in,
            check_out=r.check_out,
            nights=(r.check_out - r.check_in).days,
            room_count=n,
            currency=r.currency,
            total_amount=r.total_amount,
            created_at=r.created_at,
        )
        for r, first, last, n in rows.all()
    ]


async def _detail(db: DB, reservation: Reservation) -> ReservationDetail:
    summary = (await _summary_rows(db, [Reservation.id == reservation.id]))[0]
    guest = await db.get(Guest, reservation.guest_id)
    assert guest is not None
    rooms = await db.execute(
        select(ReservationRoom, RoomType.name, Room.number)
        .join(RoomType, RoomType.id == ReservationRoom.room_type_id)
        .outerjoin(Room, Room.id == ReservationRoom.room_id)
        .where(ReservationRoom.reservation_id == reservation.id)
        .order_by(RoomType.name, Room.number)
    )
    history = await db.execute(
        select(ReservationStatusChange, User.full_name)
        .outerjoin(User, User.id == ReservationStatusChange.changed_by)
        .where(ReservationStatusChange.reservation_id == reservation.id)
        .order_by(ReservationStatusChange.changed_at, ReservationStatusChange.id)
    )
    return ReservationDetail(
        **summary.model_dump(),
        tax_amount=reservation.tax_amount,
        notes=reservation.notes,
        cancellation_reason=reservation.cancellation_reason,
        guest=GuestOut.model_validate(guest),
        rooms=[
            ReservationRoomOut(
                id=rr.id,
                room_type_id=rr.room_type_id,
                room_type_name=type_name,
                room_id=rr.room_id,
                room_number=number,
                rate_plan_id=rr.rate_plan_id,
                adults=rr.adults,
                children=rr.children,
                total_amount=rr.total_amount,
                tax_amount=rr.tax_amount,
                price_snapshot=rr.price_snapshot,
            )
            for rr, type_name, number in rooms.all()
        ],
        history=[
            StatusChangeOut(
                from_status=h.from_status,
                to_status=h.to_status,
                reason=h.reason,
                changed_by_name=name,
                changed_at=h.changed_at,
            )
            for h, name in history.all()
        ],
    )


@router.get("/properties/{property_id}/reservations", response_model=list[ReservationSummary])
async def list_reservations(
    property_id: uuid.UUID,
    auth: CanView,
    db: DB,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
    include_cancelled: bool = False,
) -> list[ReservationSummary]:
    """Bookings whose stay overlaps [from, to)."""
    prop = await get_property(db, property_id, auth, Permission.RESERVATIONS_VIEW)
    if date_to <= date_from or (date_to - date_from).days > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="Choose a range of up to 120 days.")
    where = [Reservation.property_id == prop.id, service.overlaps(date_from, date_to)]
    if not include_cancelled:
        where.append(
            Reservation.status.notin_([ReservationStatus.CANCELLED, ReservationStatus.NO_SHOW])
        )
    return await _summary_rows(db, where)


@router.post(
    "/properties/{property_id}/reservations",
    response_model=ReservationDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation(
    property_id: uuid.UUID, body: ReservationCreate, auth: CanManage, request: Request, db: DB
) -> ReservationDetail:
    prop = await get_property(db, property_id, auth, Permission.RESERVATIONS_MANAGE)
    if body.guest_id is not None:
        guest = await db.get(Guest, body.guest_id)
        if guest is None:
            raise HTTPException(status_code=422, detail="Choose a guest from this organisation.")
    else:
        assert body.guest is not None
        guest = Guest(organisation_id=prop.organisation_id, **_guest_values(body.guest))
        db.add(guest)
        await db.flush()
    try:
        async with db.begin_nested():
            reservation = await service.create_reservation(
                db,
                prop=prop,
                guest_id=guest.id,
                check_in=body.check_in,
                check_out=body.check_out,
                rooms=[service.RoomRequest(**r.model_dump()) for r in body.rooms],
                status=body.status,
                source=body.source,
                notes=body.notes,
                user_id=auth.user.id,
            )
    except service.BookingError as exc:
        raise _booking_error(exc) from None
    except IntegrityError as exc:
        if "ex_reservation_rooms_no_double_booking" in str(exc.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That room is already booked for some of these nights.",
            ) from None
        raise
    await audit.record(
        db,
        action="reservation.created",
        organisation_id=prop.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="reservation",
        entity_id=reservation.id,
        data={"reference": reservation.reference, "status": reservation.status},
        ip_address=client_ip(request),
    )
    return await _detail(db, reservation)


def _guest_values(g: GuestIn) -> dict[str, object]:
    values = g.model_dump()
    if values.get("email"):
        values["email"] = str(values["email"]).lower()
    return values


async def _reservation(
    db: DB, auth: AuthContext, reservation_id: uuid.UUID, perm: Permission
) -> Reservation:
    reservation = await db.get(Reservation, reservation_id)
    if reservation is None:
        raise not_found("Reservation")
    auth.require_for_property(perm, reservation.property_id)
    return reservation


@router.get("/reservations/{reservation_id}", response_model=ReservationDetail)
async def read_reservation(reservation_id: uuid.UUID, auth: CanView, db: DB) -> ReservationDetail:
    reservation = await _reservation(db, auth, reservation_id, Permission.RESERVATIONS_VIEW)
    return await _detail(db, reservation)


async def _transition(
    reservation_id: uuid.UUID,
    to: ReservationStatus,
    body: StatusChange,
    auth: AuthContext,
    request: Request,
    db: DB,
) -> ReservationDetail:
    reservation = await _reservation(db, auth, reservation_id, Permission.RESERVATIONS_MANAGE)
    previous = reservation.status
    prop = await db.get(Property, reservation.property_id)
    assert prop is not None
    property_today = datetime.now(ZoneInfo(prop.timezone)).date()
    try:
        await service.change_status(
            db, reservation, to, user_id=auth.user.id, reason=body.reason, today=property_today
        )
    except service.BookingError as exc:
        raise _booking_error(exc) from None
    await audit.record(
        db,
        action=f"reservation.{to.value}",
        organisation_id=reservation.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="reservation",
        entity_id=reservation.id,
        data={"reference": reservation.reference, "from": previous, "reason": body.reason},
        ip_address=client_ip(request),
    )
    return await _detail(db, reservation)


@router.post("/reservations/{reservation_id}/confirm", response_model=ReservationDetail)
async def confirm(
    reservation_id: uuid.UUID, body: StatusChange, auth: CanManage, request: Request, db: DB
) -> ReservationDetail:
    return await _transition(reservation_id, ReservationStatus.CONFIRMED, body, auth, request, db)


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationDetail)
async def cancel(
    reservation_id: uuid.UUID, body: StatusChange, auth: CanManage, request: Request, db: DB
) -> ReservationDetail:
    return await _transition(reservation_id, ReservationStatus.CANCELLED, body, auth, request, db)


# --- room allocation --------------------------------------------------------------------


async def _reservation_room(
    db: DB, auth: AuthContext, rr_id: uuid.UUID, perm: Permission
) -> ReservationRoom:
    rr = await db.get(ReservationRoom, rr_id)
    if rr is None:
        raise not_found("Booked room")
    auth.require_for_property(perm, rr.property_id)
    return rr


@router.get("/reservation-rooms/{rr_id}/free-rooms", response_model=list[FreeRoom])
async def list_free_rooms(rr_id: uuid.UUID, auth: CanView, db: DB) -> list[FreeRoom]:
    rr = await _reservation_room(db, auth, rr_id, Permission.RESERVATIONS_VIEW)
    rooms = await service.free_rooms(db, rr)
    buildings = {
        b.id: b.name
        for b in (
            await db.scalars(select(Building).where(Building.property_id == rr.property_id))
        ).all()
    }
    return [
        FreeRoom(
            id=r.id,
            number=r.number,
            building_name=buildings.get(r.building_id) if r.building_id else None,
            floor=r.floor,
            housekeeping_status=r.housekeeping_status,
            maintenance_status=r.maintenance_status,
        )
        for r in rooms
    ]


@router.post("/reservation-rooms/{rr_id}/assign", response_model=ReservationDetail)
async def assign_room(
    rr_id: uuid.UUID, body: AssignRoom, auth: CanManage, request: Request, db: DB
) -> ReservationDetail:
    rr = await _reservation_room(db, auth, rr_id, Permission.RESERVATIONS_MANAGE)
    previous = rr.room_id
    try:
        async with db.begin_nested():
            await service.assign_room(db, rr, body.room_id)
    except service.BookingError as exc:
        raise _booking_error(exc) from None
    except IntegrityError as exc:
        if "ex_reservation_rooms_no_double_booking" in str(exc.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That room is already booked for some of these nights.",
            ) from None
        raise
    reservation = await db.get(Reservation, rr.reservation_id)
    assert reservation is not None
    numbers = {
        r.id: r.number
        for r in (
            await db.scalars(
                select(Room).where(Room.id.in_([x for x in (previous, rr.room_id) if x]))
            )
        ).all()
    }
    await audit.record(
        db,
        action="reservation.room_assigned",
        organisation_id=rr.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="reservation",
        entity_id=reservation.id,
        data={
            "reference": reservation.reference,
            "from": numbers.get(previous) if previous else None,
            "to": numbers.get(rr.room_id) if rr.room_id else None,
        },
        ip_address=client_ip(request),
    )
    return await _detail(db, reservation)


# --- calendar and today -----------------------------------------------------------------


@router.get("/properties/{property_id}/calendar", response_model=CalendarOut)
async def calendar(
    property_id: uuid.UUID,
    auth: CanView,
    db: DB,
    start: date,
    days: Annotated[int, Query(ge=1, le=31)] = 14,
) -> CalendarOut:
    prop = await get_property(db, property_id, auth, Permission.RESERVATIONS_VIEW)
    end = start + timedelta(days=days)
    rooms = await db.execute(
        select(Room, RoomType.code, Building.name)
        .join(RoomType, RoomType.id == Room.room_type_id)
        .outerjoin(Building, Building.id == Room.building_id)
        .where(Room.property_id == prop.id, Room.status == RecordStatus.ACTIVE)
        .order_by(
            RoomType.sort_order,
            RoomType.name,
            Building.sort_order.nulls_first(),
            func.length(Room.number),
            Room.number,
        )
    )
    stays = await db.execute(
        select(ReservationRoom, Reservation.reference, Guest.first_name, Guest.last_name)
        .join(Reservation, Reservation.id == ReservationRoom.reservation_id)
        .join(Guest, Guest.id == Reservation.guest_id)
        .where(
            ReservationRoom.property_id == prop.id,
            ReservationRoom.status.in_(service.ASSIGNABLE),
            ReservationRoom.check_in < end,
            ReservationRoom.check_out > start,
        )
        .order_by(ReservationRoom.check_in, Reservation.reference)
    )
    return CalendarOut(
        start=start,
        days=days,
        rooms=[
            CalendarRoom(
                id=r.id,
                number=r.number,
                room_type_id=r.room_type_id,
                room_type_code=code,
                building_name=building,
                housekeeping_status=r.housekeeping_status,
                maintenance_status=r.maintenance_status,
            )
            for r, code, building in rooms.all()
        ],
        stays=[
            CalendarStay(
                reservation_room_id=rr.id,
                reservation_id=rr.reservation_id,
                reference=ref,
                status=rr.status,
                guest_name=f"{first} {last}",
                room_type_id=rr.room_type_id,
                room_id=rr.room_id,
                check_in=rr.check_in,
                check_out=rr.check_out,
                adults=rr.adults,
                children=rr.children,
            )
            for rr, ref, first, last in stays.all()
        ],
    )


@router.get("/properties/{property_id}/today", response_model=TodayOut)
async def today(property_id: uuid.UUID, auth: CanView, db: DB) -> TodayOut:
    """Arrivals and departures for today in the property's timezone."""
    prop = await get_property(db, property_id, auth, Permission.RESERVATIONS_VIEW)
    day = datetime.now(ZoneInfo(prop.timezone)).date()
    active = [ReservationStatus.PROVISIONAL, ReservationStatus.CONFIRMED]
    arrivals = await _summary_rows(
        db,
        [
            Reservation.property_id == prop.id,
            Reservation.check_in == day,
            Reservation.status.in_([*active, ReservationStatus.CHECKED_IN]),
        ],
    )
    departures = await _summary_rows(
        db,
        [
            Reservation.property_id == prop.id,
            Reservation.check_out == day,
            Reservation.status.in_(
                [*active, ReservationStatus.CHECKED_IN, ReservationStatus.CHECKED_OUT]
            ),
        ],
    )
    in_house = await db.scalar(
        select(func.count())
        .select_from(Reservation)
        .where(
            Reservation.property_id == prop.id,
            Reservation.status == ReservationStatus.CHECKED_IN,
        )
    )
    unassigned = await db.scalar(
        select(func.count())
        .select_from(ReservationRoom)
        .where(
            ReservationRoom.property_id == prop.id,
            ReservationRoom.check_in == day,
            ReservationRoom.room_id.is_(None),
            ReservationRoom.status.in_(active),
        )
    )
    return TodayOut(
        date=day,
        arrivals=arrivals,
        departures=departures,
        in_house=int(in_house or 0),
        unassigned_arrivals=int(unassigned or 0),
    )


@router.post("/reservations/{reservation_id}/check-in", response_model=ReservationDetail)
async def check_in(
    reservation_id: uuid.UUID, body: StatusChange, auth: CanManage, request: Request, db: DB
) -> ReservationDetail:
    return await _transition(reservation_id, ReservationStatus.CHECKED_IN, body, auth, request, db)


@router.post("/reservations/{reservation_id}/check-out", response_model=ReservationDetail)
async def check_out(
    reservation_id: uuid.UUID, body: StatusChange, auth: CanManage, request: Request, db: DB
) -> ReservationDetail:
    return await _transition(reservation_id, ReservationStatus.CHECKED_OUT, body, auth, request, db)


@router.post("/reservations/{reservation_id}/no-show", response_model=ReservationDetail)
async def no_show(
    reservation_id: uuid.UUID, body: StatusChange, auth: CanManage, request: Request, db: DB
) -> ReservationDetail:
    return await _transition(reservation_id, ReservationStatus.NO_SHOW, body, auth, request, db)


@router.patch("/reservations/{reservation_id}/dates", response_model=ReservationDetail)
async def change_dates(
    reservation_id: uuid.UUID, body: DateChange, auth: CanManage, request: Request, db: DB
) -> ReservationDetail:
    reservation = await _reservation(db, auth, reservation_id, Permission.RESERVATIONS_MANAGE)
    prop = await db.get(Property, reservation.property_id)
    assert prop is not None
    try:
        async with db.begin_nested():
            old_total, new_total = await service.change_dates(
                db,
                prop=prop,
                reservation=reservation,
                check_in=body.check_in,
                check_out=body.check_out,
                user_id=auth.user.id,
            )
    except service.BookingError as exc:
        raise _booking_error(exc) from None
    except IntegrityError as exc:
        if "ex_reservation_rooms_no_double_booking" in str(exc.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An assigned room is taken on the new dates. Remove or change it first.",
            ) from None
        raise
    await db.refresh(reservation)
    await audit.record(
        db,
        action="reservation.dates_changed",
        organisation_id=reservation.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="reservation",
        entity_id=reservation.id,
        data={
            "reference": reservation.reference,
            "check_in": str(body.check_in),
            "check_out": str(body.check_out),
            "old_total": str(old_total),
            "new_total": str(new_total),
        },
        ip_address=client_ip(request),
    )
    return await _detail(db, reservation)


@router.patch("/guests/{guest_id}", response_model=GuestOut)
async def update_guest(
    guest_id: uuid.UUID, body: GuestUpdate, auth: CanManage, request: Request, db: DB
) -> Guest:
    """Guests belong to the organisation; anyone who manages reservations at any of its
    properties may correct their details."""
    guest = await db.get(Guest, guest_id)
    if guest is None:
        raise not_found("Guest")
    changes = body.model_dump(exclude_unset=True)
    for required in ("first_name", "last_name"):
        if required in changes and not changes[required]:
            raise HTTPException(status_code=422, detail="First and last name are required.")
    if changes.get("email"):
        changes["email"] = str(changes["email"]).lower()
    diff = audit.apply_changes(guest, changes)
    if diff["after"]:
        await db.flush()
        await audit.record(
            db,
            action="guest.updated",
            organisation_id=guest.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="guest",
            entity_id=guest.id,
            # Field names only: guest details are personal data and stay out of the log.
            data={"fields": sorted(diff["after"])},
            ip_address=client_ip(request),
        )
    return guest
