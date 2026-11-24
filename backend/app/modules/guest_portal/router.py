"""Guest portal (ADR-0013): a booking opened by its secret link, and staff link management."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.core.errors import not_found
from app.core.rate_limit import hit
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, Auth, client_ip
from app.modules.auth.permissions import Permission
from app.modules.guest_portal import service
from app.modules.guest_portal.schemas import (
    ArrivalUpdate,
    CancellationRequest,
    GuestLink,
    GuestLinkRevoked,
    PortalBooking,
    PortalInvoice,
    PortalProperty,
    PortalRoom,
)
from app.modules.guests.models import Guest
from app.modules.invoicing.models import Invoice, InvoiceStatus
from app.modules.invoicing.service import credited_total
from app.modules.notifications.service import venue_of
from app.modules.payments import service as payments
from app.modules.payments.models import Payment, Refund
from app.modules.properties.models import Property
from app.modules.reservations.models import Reservation, ReservationRoom, ReservationStatus

router = APIRouter(prefix="/api/v1", tags=["guest portal"])
ZERO = Decimal("0.00")
GONE = "This link has expired or was withdrawn. Please contact the property."
OPEN = (ReservationStatus.PROVISIONAL, ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN)


async def _open(db: DB, request: Request, token: str) -> Reservation:
    if not await hit(f"portal:{client_ip(request)}", limit=60, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a moment.")
    reservation_id = await service.resolve(db, token)
    if reservation_id is None:
        raise HTTPException(status_code=404, detail=GONE)
    r = await db.get(Reservation, reservation_id)
    assert r is not None
    return r


async def _portal(db: DB, r: Reservation) -> PortalBooking:
    prop = await db.get(Property, r.property_id)
    guest = await db.get(Guest, r.guest_id)
    assert prop is not None and guest is not None
    rooms = (
        await db.scalars(
            select(ReservationRoom)
            .where(ReservationRoom.reservation_id == r.id)
            .order_by(ReservationRoom.check_in, ReservationRoom.id)
        )
    ).all()
    invoices = []
    for inv in (
        await db.scalars(
            select(Invoice)
            .where(Invoice.reservation_id == r.id, Invoice.status == InvoiceStatus.ISSUED)
            .order_by(Invoice.issued_at)
        )
    ).all():
        assert inv.number is not None and inv.issue_date is not None
        invoices.append(
            PortalInvoice(
                number=inv.number,
                issue_date=inv.issue_date,
                total=inv.total,
                credited=await credited_total(db, inv.id),
                paid=await payments.paid_total(db, inv.id),
                balance=max(await payments.balance(db, inv), ZERO),
            )
        )
    received = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), ZERO)).where(
            Payment.reservation_id == r.id, Payment.reversed_at.is_(None)
        )
    )
    refunded = await db.scalar(
        select(func.coalesce(func.sum(Refund.amount), ZERO))
        .join(Payment, Payment.id == Refund.payment_id)
        .where(Payment.reservation_id == r.id)
    )
    venue = venue_of(prop)
    return PortalBooking(
        reference=r.reference,
        status=r.status,
        guest_name=f"{guest.first_name} {guest.last_name}",
        check_in=r.check_in,
        check_out=r.check_out,
        nights=(r.check_out - r.check_in).days,
        currency=r.currency,
        total=r.total_amount,
        rooms=[
            PortalRoom(
                room_type=rr.price_snapshot["room_type"],
                rate_plan=rr.price_snapshot["rate_plan"],
                adults=rr.adults,
                children=rr.children,
                total=rr.total_amount,
            )
            for rr in rooms
        ],
        invoices=invoices,
        paid=(received or ZERO) - (refunded or ZERO),
        property=PortalProperty(
            name=prop.name,
            address=venue.address,
            phone=prop.phone,
            email=prop.email,
            check_in_time=prop.check_in_time,
            check_out_time=prop.check_out_time,
            booking_terms=prop.booking_terms,
        ),
        arrival_time=r.guest_arrival_time,
        message=r.guest_message,
        cancellation_requested=r.cancellation_requested_at is not None,
        cancellation_reason=r.cancellation_request_reason,
        can_update=r.status in OPEN,
    )


async def _guest_change(db: DB, request: Request, r: Reservation, action: str) -> None:
    if r.status not in OPEN:
        raise HTTPException(status_code=409, detail="This booking can no longer be changed online.")
    if not await hit(f"portal-update:{r.id}", limit=10, window_seconds=3600):
        raise HTTPException(
            status_code=429, detail="Too many changes. Please contact the property."
        )
    await audit.record(
        db,
        action=action,
        organisation_id=r.organisation_id,
        actor_user_id=None,
        entity_type="reservation",
        entity_id=r.id,
        data={"reference": r.reference, "via": "guest_portal"},
        ip_address=client_ip(request),
    )


@router.get("/stay/{token}", response_model=PortalBooking)
async def view(token: str, request: Request, db: DB) -> PortalBooking:
    return await _portal(db, await _open(db, request, token))


@router.post("/stay/{token}/arrival", response_model=PortalBooking)
async def arrival(token: str, body: ArrivalUpdate, request: Request, db: DB) -> PortalBooking:
    r = await _open(db, request, token)
    await _guest_change(db, request, r, "reservation.guest_updated")
    r.guest_arrival_time = body.arrival_time
    r.guest_message = body.message or None
    r.guest_updated_at = datetime.now(UTC)
    await db.flush()
    return await _portal(db, r)


@router.post("/stay/{token}/cancellation-request", response_model=PortalBooking)
async def request_cancellation(
    token: str, body: CancellationRequest, request: Request, db: DB
) -> PortalBooking:
    r = await _open(db, request, token)
    if r.status == ReservationStatus.CHECKED_IN:
        raise HTTPException(status_code=409, detail="Please speak to reception during your stay.")
    await _guest_change(db, request, r, "reservation.cancellation_requested")
    r.cancellation_requested_at = datetime.now(UTC)
    r.cancellation_request_reason = body.reason
    await db.flush()
    return await _portal(db, r)


# --- staff -------------------------------------------------------------------------------


async def _staff_reservation(db: DB, auth: Auth, reservation_id: uuid.UUID) -> Reservation:
    r = await db.get(Reservation, reservation_id)
    if r is None:
        raise not_found("Reservation")
    auth.require_for_property(Permission.RESERVATIONS_MANAGE, r.property_id)
    return r


@router.post(
    "/reservations/{reservation_id}/guest-links", response_model=GuestLink, status_code=201
)
async def create_guest_link(
    reservation_id: uuid.UUID, auth: Auth, request: Request, db: DB
) -> GuestLink:
    r = await _staff_reservation(db, auth, reservation_id)
    url, expires = await service.create_link(db, r, user_id=auth.user.id)
    await audit.record(
        db,
        action="reservation.guest_link_created",
        organisation_id=r.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="reservation",
        entity_id=r.id,
        data={"reference": r.reference},
        ip_address=client_ip(request),
    )
    return GuestLink(url=url, expires_at=expires)


@router.post("/reservations/{reservation_id}/guest-links/revoke", response_model=GuestLinkRevoked)
async def revoke_guest_links(
    reservation_id: uuid.UUID, auth: Auth, request: Request, db: DB
) -> GuestLinkRevoked:
    r = await _staff_reservation(db, auth, reservation_id)
    count = await service.revoke_all(db, r)
    await audit.record(
        db,
        action="reservation.guest_links_revoked",
        organisation_id=r.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="reservation",
        entity_id=r.id,
        data={"reference": r.reference, "revoked": count},
        ip_address=client_ip(request),
    )
    return GuestLinkRevoked(revoked=count, reservation_id=r.id)


@router.post("/reservations/{reservation_id}/cancellation-request/dismiss", status_code=204)
async def dismiss_cancellation_request(
    reservation_id: uuid.UUID, auth: Auth, request: Request, db: DB
) -> None:
    r = await _staff_reservation(db, auth, reservation_id)
    r.cancellation_requested_at = None
    r.cancellation_request_reason = None
    await db.flush()
    await audit.record(
        db,
        action="reservation.cancellation_request_dismissed",
        organisation_id=r.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="reservation",
        entity_id=r.id,
        data={"reference": r.reference},
        ip_address=client_ip(request),
    )
