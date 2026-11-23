"""Emailing booking confirmations, invoices and receipts (ADR-0011).

Each endpoint renders the message from current data, writes it to the outbox and returns
at once; the worker delivers it. Permissions follow the subject of the message.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select

from app.core.errors import not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, Auth, AuthContext, client_ip
from app.modules.auth.permissions import Permission
from app.modules.guest_portal import service as guest_links
from app.modules.guests.models import Guest
from app.modules.invoicing.models import Invoice, InvoiceItem, InvoiceStatus
from app.modules.invoicing.service import credited_total
from app.modules.notifications import service, templates
from app.modules.notifications.models import Notification, NotificationKind
from app.modules.payments import service as payments
from app.modules.payments.models import Payment, PaymentAllocation
from app.modules.properties.models import Property
from app.modules.reservations.models import Reservation, ReservationRoom, ReservationStatus

router = APIRouter(prefix="/api/v1", tags=["notifications"])
Key = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
METHOD_WORDS = {
    "cash": "Cash",
    "card": "Card",
    "bank_transfer": "Bank transfer",
    "mobile_money": "Mobile money",
    "other": "Other",
}


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Defaults to the guest's email address.
    to: EmailStr | None = None
    idempotency_key: Key


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    subject_type: str
    subject_id: uuid.UUID
    recipient: str
    title: str
    body_text: str
    status: str
    attempts: int
    last_error: str | None
    provider: str | None
    created_at: datetime
    sent_at: datetime | None
    next_attempt_at: datetime


_venue = service.venue_of


def _recipient(requested: str | None, fallback: str | None) -> str:
    to = requested or fallback
    if not to:
        raise HTTPException(
            status_code=422, detail="There is no email address on file. Enter one to send to."
        )
    return to


async def _send(
    db: DB,
    auth: AuthContext,
    request: Request,
    response: Response,
    *,
    prop: Property,
    kind: NotificationKind,
    subject_type: str,
    subject_id: uuid.UUID,
    recipient: str,
    rendered: templates.Rendered,
    key: str,
) -> Notification:
    row, created = await service.queue(
        db,
        prop=prop,
        kind=kind,
        subject_type=subject_type,
        subject_id=subject_id,
        recipient=recipient,
        rendered=rendered,
        idempotency_key=key,
        user_id=auth.user.id,
    )
    if created:
        response.status_code = status.HTTP_202_ACCEPTED
        await audit.record(
            db,
            action="notification.queued",
            organisation_id=prop.organisation_id,
            actor_user_id=auth.user.id,
            entity_type=subject_type,
            entity_id=subject_id,
            # Recipient addresses are personal data; the log keeps only the kind.
            data={"kind": kind.value, "title": rendered.subject},
            ip_address=client_ip(request),
        )
    return row


@router.post("/reservations/{reservation_id}/email-confirmation", response_model=NotificationOut)
async def email_confirmation(
    reservation_id: uuid.UUID,
    body: SendRequest,
    auth: Auth,
    request: Request,
    response: Response,
    db: DB,
) -> Notification:
    r = await db.get(Reservation, reservation_id)
    if r is None:
        raise not_found("Reservation")
    auth.require_for_property(Permission.RESERVATIONS_MANAGE, r.property_id)
    if r.status not in (ReservationStatus.PROVISIONAL, ReservationStatus.CONFIRMED):
        raise HTTPException(
            status_code=409, detail="Only provisional or confirmed bookings get a confirmation."
        )
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
    manage_url, _ = await guest_links.create_link(db, r, user_id=auth.user.id)
    rendered = templates.booking_confirmation(
        manage_url=manage_url,
        venue=_venue(prop),
        guest_name=f"{guest.first_name} {guest.last_name}",
        reference=r.reference,
        provisional=r.status == ReservationStatus.PROVISIONAL,
        check_in=r.check_in,
        check_out=r.check_out,
        check_in_time=prop.check_in_time,
        check_out_time=prop.check_out_time,
        rooms=[
            templates.StayLine(
                room_type=rr.price_snapshot["room_type"],
                rate_plan=rr.price_snapshot["rate_plan"],
                adults=rr.adults,
                children=rr.children,
                total=rr.total_amount,
            )
            for rr in rooms
        ],
        currency=r.currency,
        total=r.total_amount,
    )
    return await _send(
        db,
        auth,
        request,
        response,
        prop=prop,
        kind=NotificationKind.BOOKING_CONFIRMATION,
        subject_type="reservation",
        subject_id=r.id,
        recipient=_recipient(body.to, guest.email),
        rendered=rendered,
        key=body.idempotency_key,
    )


@router.post("/invoices/{invoice_id}/email", response_model=NotificationOut)
async def email_invoice(
    invoice_id: uuid.UUID,
    body: SendRequest,
    auth: Auth,
    request: Request,
    response: Response,
    db: DB,
) -> Notification:
    inv = await db.get(Invoice, invoice_id)
    if inv is None:
        raise not_found("Invoice")
    auth.require_for_property(Permission.INVOICES_MANAGE, inv.property_id)
    if inv.status != InvoiceStatus.ISSUED or inv.number is None or inv.issue_date is None:
        raise HTTPException(status_code=409, detail="Issue the invoice before emailing it.")
    prop = await db.get(Property, inv.property_id)
    assert prop is not None
    guest = await db.get(Guest, inv.guest_id) if inv.guest_id else None
    items = (
        await db.scalars(
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == inv.id)
            .order_by(InvoiceItem.position)
        )
    ).all()
    taxes: dict[tuple[str, Decimal], Decimal] = {}
    for i in items:
        for t in i.taxes:
            k = (t["name"], Decimal(t["rate_percent"]))
            taxes[k] = taxes.get(k, Decimal("0.00")) + Decimal(t["amount"])
    reference = (
        await db.scalar(select(Reservation.reference).where(Reservation.id == inv.reservation_id))
        if inv.reservation_id
        else None
    )
    rendered = templates.invoice(
        venue=_venue(prop),
        number=inv.number,
        tax_invoice=bool(prop.tax_number),
        issue_date=inv.issue_date,
        due_date=inv.due_date,
        bill_to=inv.bill_to_name,
        lines=[templates.InvoiceLine(i.description, i.total_amount) for i in items],
        net=inv.net_total,
        taxes=[(name, rate, amount) for (name, rate), amount in taxes.items()],
        total=inv.total,
        credited=await credited_total(db, inv.id),
        paid=await payments.paid_total(db, inv.id),
        balance=await payments.balance(db, inv),
        currency=inv.currency,
        reference=reference,
    )
    return await _send(
        db,
        auth,
        request,
        response,
        prop=prop,
        kind=NotificationKind.INVOICE,
        subject_type="invoice",
        subject_id=inv.id,
        recipient=_recipient(body.to, guest.email if guest else None),
        rendered=rendered,
        key=body.idempotency_key,
    )


@router.post("/payments/{payment_id}/email-receipt", response_model=NotificationOut)
async def email_receipt(
    payment_id: uuid.UUID,
    body: SendRequest,
    auth: Auth,
    request: Request,
    response: Response,
    db: DB,
) -> Notification:
    p = await db.get(Payment, payment_id)
    if p is None:
        raise not_found("Payment")
    auth.require_for_property(Permission.PAYMENTS_MANAGE, p.property_id)
    if p.reversed_at is not None:
        raise HTTPException(status_code=409, detail="A reversed payment has no receipt.")
    prop = await db.get(Property, p.property_id)
    assert prop is not None
    reservation = await db.get(Reservation, p.reservation_id) if p.reservation_id else None
    guest = await db.get(Guest, reservation.guest_id) if reservation else None
    applied = (
        await db.execute(
            select(Invoice.number, func.sum(PaymentAllocation.amount))
            .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
            .where(PaymentAllocation.payment_id == p.id)
            .group_by(Invoice.number)
            .having(func.sum(PaymentAllocation.amount) > 0)
            .order_by(Invoice.number)
        )
    ).all()
    rendered = templates.receipt(
        venue=_venue(prop),
        payer=p.payer_name,
        amount=p.amount,
        currency=p.currency,
        method=METHOD_WORDS.get(p.method, p.method),
        received_on=p.received_on,
        reference=p.reference,
        applied_to=[(number or "", amount) for number, amount in applied],
        booking_reference=reservation.reference if reservation else None,
    )
    return await _send(
        db,
        auth,
        request,
        response,
        prop=prop,
        kind=NotificationKind.RECEIPT,
        subject_type="payment",
        subject_id=p.id,
        recipient=_recipient(body.to, guest.email if guest else None),
        rendered=rendered,
        key=body.idempotency_key,
    )


VIEW_PERMISSION: dict[str, tuple[type[Reservation] | type[Invoice] | type[Payment], Permission]] = {
    "reservation": (Reservation, Permission.RESERVATIONS_VIEW),
    "invoice": (Invoice, Permission.INVOICES_VIEW),
    "payment": (Payment, Permission.PAYMENTS_VIEW),
}


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    auth: Auth,
    db: DB,
    subject_type: Literal["reservation", "invoice", "payment"],
    subject_id: uuid.UUID,
) -> list[Notification]:
    model, perm = VIEW_PERMISSION[subject_type]
    property_id = await db.scalar(select(model.property_id).where(model.id == subject_id))
    if property_id is None:
        raise not_found("Record")
    auth.require_for_property(perm, property_id)
    rows = await db.scalars(
        select(Notification)
        .where(Notification.subject_type == subject_type, Notification.subject_id == subject_id)
        .order_by(Notification.created_at.desc())
    )
    return list(rows.all())
