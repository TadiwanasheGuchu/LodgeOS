"""Public booking engine (ADR-0012). No sign-in: each request resolves one enabled property
through ``public_booking_property`` and runs under that organisation's RLS context."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.db import set_tenant_context
from app.core.rate_limit import hit
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, client_ip
from app.modules.booking_engine.schemas import (
    Offer,
    PublicBooking,
    PublicBookingCreate,
    PublicBookingRoom,
    PublicProperty,
    PublicRoomType,
    RoomTypeOffers,
)
from app.modules.guest_portal import service as guest_links
from app.modules.guests.models import Guest
from app.modules.notifications import service as notifications
from app.modules.notifications import templates
from app.modules.notifications.models import NotificationKind
from app.modules.properties.models import Property, RecordStatus
from app.modules.rates import pricing
from app.modules.rates.models import RatePlan
from app.modules.rates.service import price_stay
from app.modules.reservations import service as bookings
from app.modules.reservations.models import Reservation, ReservationRoom, ReservationStatus
from app.modules.rooms.models import RoomType

router = APIRouter(prefix="/api/v1/public", tags=["booking engine"])
NOT_AVAILABLE = "This booking page is not available."
MAX_NIGHTS = 30


async def _property(db: DB, org_slug: str, property_slug: str) -> Property:
    row = (
        await db.execute(
            text("SELECT organisation_id, property_id FROM public_booking_property(:o, :p)"),
            {"o": org_slug, "p": property_slug},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=NOT_AVAILABLE)
    await set_tenant_context(db, user_id=None, organisation_id=row.organisation_id)
    prop = await db.get(Property, row.property_id)
    assert prop is not None
    return prop


def _today(prop: Property) -> date:
    return datetime.now(ZoneInfo(prop.timezone)).date()


def _window(prop: Property) -> tuple[date, date]:
    today = _today(prop)
    return today + timedelta(days=prop.min_lead_days), today + timedelta(days=prop.max_advance_days)


def _check_dates(prop: Property, check_in: date, check_out: date) -> None:
    first, last = _window(prop)
    if check_out <= check_in:
        raise HTTPException(status_code=422, detail="Departure must be after arrival.")
    if (check_out - check_in).days > MAX_NIGHTS:
        raise HTTPException(
            status_code=422,
            detail=f"Online bookings are up to {MAX_NIGHTS} nights. Please contact us.",
        )
    if check_in < first:
        raise HTTPException(
            status_code=422, detail=f"The earliest arrival we can take online is {first:%d %B %Y}."
        )
    if check_in > last:
        raise HTTPException(
            status_code=422, detail=f"We take online bookings up to {last:%d %B %Y}."
        )


async def _limit(request: Request, key: str, limit: int, window: int) -> None:
    if not await hit(f"public:{key}", limit=limit, window_seconds=window):
        raise HTTPException(
            status_code=429, detail="Too many requests. Please wait a moment and try again."
        )


async def _room_types(db: DB, prop: Property) -> list[RoomType]:
    rows = await db.scalars(
        select(RoomType)
        .where(RoomType.property_id == prop.id, RoomType.status == RecordStatus.ACTIVE)
        .order_by(RoomType.sort_order, RoomType.name)
    )
    return [rt for rt in rows.all() if await bookings.sellable_rooms(db, rt.id) > 0]


async def _online_plans(db: DB, prop: Property) -> list[RatePlan]:
    rows = await db.scalars(
        select(RatePlan)
        .where(
            RatePlan.property_id == prop.id,
            RatePlan.status == RecordStatus.ACTIVE,
            RatePlan.sell_online.is_(True),
        )
        .order_by(RatePlan.name)
    )
    return list(rows.all())


@router.get("/properties/{org_slug}/{property_slug}", response_model=PublicProperty)
async def public_property(org_slug: str, property_slug: str, db: DB) -> PublicProperty:
    prop = await _property(db, org_slug, property_slug)
    first, last = _window(prop)
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
    return PublicProperty(
        name=prop.name,
        property_type=prop.property_type,
        description=prop.public_description,
        address=address,
        phone=prop.phone,
        email=prop.email,
        check_in_time=prop.check_in_time,
        check_out_time=prop.check_out_time,
        currency=prop.currency,
        timezone=prop.timezone,
        booking_mode=prop.booking_mode,
        booking_terms=prop.booking_terms or "",
        today=_today(prop),
        earliest_arrival=first,
        latest_arrival=last,
        room_types=[
            PublicRoomType(
                id=rt.id,
                name=rt.name,
                description=rt.description,
                bed_configuration=rt.bed_configuration,
                max_occupancy=rt.max_occupancy,
                max_adults=rt.max_adults,
                max_children=rt.max_children,
            )
            for rt in await _room_types(db, prop)
        ],
    )


@router.get("/properties/{org_slug}/{property_slug}/offers", response_model=list[RoomTypeOffers])
async def offers(
    org_slug: str,
    property_slug: str,
    request: Request,
    db: DB,
    check_in: date,
    check_out: date,
    adults: Annotated[int, Query(ge=1, le=20)] = 2,
    children: Annotated[int, Query(ge=0, le=20)] = 0,
) -> list[RoomTypeOffers]:
    await _limit(request, f"search:{client_ip(request)}", 60, 60)
    prop = await _property(db, org_slug, property_slug)
    _check_dates(prop, check_in, check_out)
    plans = await _online_plans(db, prop)
    out = []
    for rt in await _room_types(db, prop):
        if (
            adults > rt.max_adults
            or children > rt.max_children
            or adults + children > rt.max_occupancy
        ):
            continue
        nights = await bookings.availability(db, rt.id, check_in, check_out)
        available = max(0, min(n.sellable - n.booked for n in nights)) if nights else 0
        room_offers = []
        if available > 0:
            for plan in plans:
                try:
                    priced = await price_stay(
                        db,
                        prop,
                        rate_plan_id=plan.id,
                        room_type_id=rt.id,
                        check_in=check_in,
                        check_out=check_out,
                        adults=adults,
                        children=children,
                    )
                except pricing.QuoteError:
                    continue  # no price for this room type, outside the plan's rules, etc.
                room_offers.append(
                    Offer(
                        rate_plan_id=plan.id,
                        name=plan.name,
                        description=plan.description,
                        meal_plan=plan.meal_plan,
                        total=priced.quote.total,
                        tax_included=priced.quote.tax_total,
                        nights=len(priced.quote.nights),
                    )
                )
        out.append(
            RoomTypeOffers(
                room_type_id=rt.id,
                name=rt.name,
                available=available if room_offers else 0,
                offers=sorted(room_offers, key=lambda o: o.total),
            )
        )
    return out


async def _public_out(db: DB, r: Reservation, guest: Guest) -> PublicBooking:
    rooms = (
        await db.scalars(
            select(ReservationRoom)
            .where(ReservationRoom.reservation_id == r.id)
            .order_by(ReservationRoom.check_in, ReservationRoom.id)
        )
    ).all()
    return PublicBooking(
        reference=r.reference,
        status=r.status,
        check_in=r.check_in,
        check_out=r.check_out,
        nights=(r.check_out - r.check_in).days,
        currency=r.currency,
        total=r.total_amount,
        rooms=[
            PublicBookingRoom(
                room_type=rr.price_snapshot["room_type"],
                rate_plan=rr.price_snapshot["rate_plan"],
                adults=rr.adults,
                children=rr.children,
                total=rr.total_amount,
            )
            for rr in rooms
        ],
        guest_name=f"{guest.first_name} {guest.last_name}",
        email=guest.email or "",
        hold_expires_at=r.hold_expires_at,
    )


@router.post("/properties/{org_slug}/{property_slug}/bookings", response_model=PublicBooking)
async def book(
    org_slug: str,
    property_slug: str,
    body: PublicBookingCreate,
    request: Request,
    response: Response,
    db: DB,
) -> PublicBooking:
    await _limit(request, f"book:{client_ip(request)}", 5, 3600)
    prop = await _property(db, org_slug, property_slug)

    # A repeated submission returns the booking it already made.
    existing = await db.scalar(
        select(Reservation).where(
            Reservation.organisation_id == prop.organisation_id,
            Reservation.idempotency_key == body.idempotency_key,
        )
    )
    if existing is not None and existing.property_id == prop.id:
        guest = await db.get(Guest, existing.guest_id)
        assert guest is not None
        return await _public_out(db, existing, guest)

    if body.website:
        # Looks like a bot; give it nothing useful.
        raise HTTPException(status_code=422, detail="Please check the form and try again.")
    if not body.accept_terms:
        raise HTTPException(status_code=422, detail="Please accept the booking terms.")
    _check_dates(prop, body.check_in, body.check_out)
    await _limit(request, f"book-property:{prop.id}", 30, 3600)
    online = {p.id for p in await _online_plans(db, prop)}
    if any(r.rate_plan_id not in online for r in body.rooms):
        raise HTTPException(status_code=422, detail="That rate is not available online.")

    g = body.guest
    guest = Guest(
        organisation_id=prop.organisation_id,
        first_name=g.first_name,
        last_name=g.last_name,
        email=str(g.email).lower(),
        phone=g.phone,
        country_code=g.country_code,
    )
    db.add(guest)
    await db.flush()
    instant = prop.booking_mode == "instant"
    try:
        async with db.begin_nested():
            reservation = await bookings.create_reservation(
                db,
                prop=prop,
                guest_id=guest.id,
                check_in=body.check_in,
                check_out=body.check_out,
                rooms=[bookings.RoomRequest(**r.model_dump()) for r in body.rooms],
                status=ReservationStatus.CONFIRMED if instant else ReservationStatus.PROVISIONAL,
                source="website",
                notes=f"Guest request: {body.special_requests}" if body.special_requests else None,
                user_id=None,
            )
            reservation.idempotency_key = body.idempotency_key
            if not instant:
                reservation.hold_expires_at = datetime.now(UTC) + timedelta(
                    hours=prop.request_hold_hours
                )
            await db.flush()
    except bookings.BookingError as exc:
        detail = str(exc)
        if exc.status == 409:
            detail = "Sorry, those rooms were just taken. Please search again."
        raise HTTPException(status_code=exc.status, detail=detail) from None
    except IntegrityError:
        raise HTTPException(
            status_code=409, detail="Sorry, those rooms were just taken. Please search again."
        ) from None

    await audit.record(
        db,
        action="reservation.created",
        organisation_id=prop.organisation_id,
        actor_user_id=None,
        entity_type="reservation",
        entity_id=reservation.id,
        data={"reference": reservation.reference, "status": reservation.status, "via": "website"},
        ip_address=client_ip(request),
    )
    out = await _public_out(db, reservation, guest)
    manage_url, _ = await guest_links.create_link(db, reservation, user_id=None)
    await notifications.queue(
        db,
        prop=prop,
        kind=NotificationKind.BOOKING_CONFIRMATION,
        subject_type="reservation",
        subject_id=reservation.id,
        recipient=out.email,
        rendered=templates.booking_confirmation(
            manage_url=manage_url,
            venue=notifications.venue_of(prop),
            guest_name=out.guest_name,
            reference=out.reference,
            provisional=not instant,
            check_in=out.check_in,
            check_out=out.check_out,
            check_in_time=prop.check_in_time,
            check_out_time=prop.check_out_time,
            rooms=[
                templates.StayLine(r.room_type, r.rate_plan, r.adults, r.children, r.total)
                for r in out.rooms
            ],
            currency=out.currency,
            total=out.total,
        ),
        idempotency_key=f"web-{uuid.uuid5(uuid.NAMESPACE_URL, str(reservation.id)).hex}",
        user_id=None,
    )
    response.status_code = status.HTTP_201_CREATED
    return out
