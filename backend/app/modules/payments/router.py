"""Payments, allocations, refunds and the daily cash-up (ADR-0010)."""

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select

from app.core.errors import not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission_anywhere
from app.modules.auth.models import User
from app.modules.auth.permissions import Permission
from app.modules.guests.models import Guest
from app.modules.invoicing.models import Invoice
from app.modules.invoicing.service import credited_total
from app.modules.payments import service
from app.modules.payments.models import Payment, PaymentAllocation, Refund
from app.modules.payments.schemas import (
    AllocationChange,
    AllocationOut,
    CashUp,
    CashUpDay,
    InvoicePayments,
    MethodTotal,
    PaymentCreate,
    PaymentOut,
    RefundCreate,
    RefundOut,
    ReverseRequest,
)
from app.modules.properties.models import Property
from app.modules.properties.router import get_property
from app.modules.reservations.models import Reservation

router = APIRouter(prefix="/api/v1", tags=["payments"])

CanView = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.PAYMENTS_VIEW))]
CanManage = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.PAYMENTS_MANAGE))]
CanRefund = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.PAYMENTS_REFUND))]
ZERO = Decimal("0.00")
MAX_DAYS = 93


def _error(exc: service.PaymentError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


def _today(prop: Property) -> date:
    return datetime.now(ZoneInfo(prop.timezone)).date()


async def _payment(db: DB, auth: AuthContext, payment_id: uuid.UUID, perm: Permission) -> Payment:
    p = await db.get(Payment, payment_id)
    if p is None:
        raise not_found("Payment")
    auth.require_for_property(perm, p.property_id)
    return p


async def _invoice_of(db: DB, payment: Payment, invoice_id: uuid.UUID) -> Invoice:
    inv = await db.get(Invoice, invoice_id)
    if inv is None or inv.property_id != payment.property_id:
        raise HTTPException(status_code=422, detail="Choose an invoice of this property.")
    return inv


async def _out(db: DB, payments: list[Payment]) -> list[PaymentOut]:
    if not payments:
        return []
    ids = [p.id for p in payments]
    names = dict(
        (
            await db.execute(
                select(User.id, User.full_name).where(
                    User.id.in_({p.recorded_by for p in payments})
                )
            )
        ).all()
    )
    refs = dict(
        (
            await db.execute(
                select(Reservation.id, Reservation.reference).where(
                    Reservation.id.in_({p.reservation_id for p in payments if p.reservation_id})
                )
            )
        ).all()
    )
    allocations: dict[uuid.UUID, list[AllocationOut]] = defaultdict(list)
    for a, number, who in (
        await db.execute(
            select(PaymentAllocation, Invoice.number, User.full_name)
            .join(Invoice, Invoice.id == PaymentAllocation.invoice_id)
            .join(User, User.id == PaymentAllocation.created_by)
            .where(PaymentAllocation.payment_id.in_(ids))
            .order_by(PaymentAllocation.created_at)
        )
    ).all():
        allocations[a.payment_id].append(
            AllocationOut(
                invoice_id=a.invoice_id,
                invoice_number=number,
                amount=a.amount,
                created_at=a.created_at,
                created_by_name=who,
            )
        )
    refunds: dict[uuid.UUID, list[RefundOut]] = defaultdict(list)
    for r in (
        await db.scalars(
            select(Refund).where(Refund.payment_id.in_(ids)).order_by(Refund.recorded_at)
        )
    ).all():
        refunds[r.payment_id].append(RefundOut.model_validate(r))
    out = []
    for p in payments:
        allocated = sum((a.amount for a in allocations[p.id]), ZERO)
        refunded = sum((r.amount for r in refunds[p.id]), ZERO)
        st = service.PaymentState(allocated, refunded)
        out.append(
            PaymentOut(
                id=p.id,
                property_id=p.property_id,
                reservation_id=p.reservation_id,
                reservation_reference=refs.get(p.reservation_id) if p.reservation_id else None,
                method=p.method,
                currency=p.currency,
                amount=p.amount,
                received_on=p.received_on,
                payer_name=p.payer_name,
                reference=p.reference,
                note=p.note,
                recorded_by_name=names.get(p.recorded_by, ""),
                recorded_at=p.recorded_at,
                reversed_at=p.reversed_at,
                reversal_reason=p.reversal_reason,
                allocated=allocated,
                refunded=refunded,
                unallocated=st.unallocated(p),
                allocations=allocations[p.id],
                refunds=refunds[p.id],
            )
        )
    return out


async def _one(db: DB, payment: Payment) -> PaymentOut:
    return (await _out(db, [payment]))[0]


async def _audit(
    db: DB, auth: AuthContext, request: Request, action: str, p: Payment, **data: object
) -> None:
    await audit.record(
        db,
        action=action,
        organisation_id=p.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="payment",
        entity_id=p.id,
        data={"amount": str(p.amount), "currency": p.currency, "method": p.method, **data},
        ip_address=client_ip(request),
    )


@router.post("/properties/{property_id}/payments", response_model=PaymentOut)
async def record_payment(
    property_id: uuid.UUID,
    body: PaymentCreate,
    auth: CanManage,
    request: Request,
    response: Response,
    db: DB,
) -> PaymentOut:
    prop = await get_property(db, property_id, auth, Permission.PAYMENTS_MANAGE)
    reservation = None
    invoice = None
    if body.reservation_id is not None:
        reservation = await db.get(Reservation, body.reservation_id)
        if reservation is None or reservation.property_id != prop.id:
            raise HTTPException(status_code=422, detail="Choose a booking of this property.")
    if body.invoice_id is not None:
        invoice = await db.get(Invoice, body.invoice_id)
        if invoice is None or invoice.property_id != prop.id:
            raise HTTPException(status_code=422, detail="Choose an invoice of this property.")
        auth.require_for_property(Permission.INVOICES_VIEW, prop.id)
    currency = (
        invoice.currency if invoice else reservation.currency if reservation else prop.currency
    )
    payer = body.payer_name
    if payer is None and invoice is not None:
        payer = invoice.bill_to_name
    if payer is None and reservation is not None:
        guest = await db.get(Guest, reservation.guest_id)
        payer = f"{guest.first_name} {guest.last_name}" if guest else None
    if payer is None:
        raise HTTPException(status_code=422, detail="Say who paid.")
    today = _today(prop)
    if body.received_on is not None and body.received_on > today:
        raise HTTPException(status_code=422, detail="A payment cannot be received in the future.")
    try:
        payment, created = await service.record(
            db,
            {
                "organisation_id": prop.organisation_id,
                "property_id": prop.id,
                "reservation_id": reservation.id
                if reservation
                else invoice.reservation_id
                if invoice
                else None,
                "method": body.method,
                "currency": currency,
                "amount": body.amount,
                "received_on": body.received_on or today,
                "payer_name": payer,
                "reference": body.reference,
                "note": body.note,
                "idempotency_key": body.idempotency_key,
                "recorded_by": auth.user.id,
            },
        )
        if created and invoice is not None:
            owed = await service.balance(db, invoice)
            if owed > ZERO:
                await service.allocate(
                    db, payment, invoice, min(owed, body.amount), user_id=auth.user.id
                )
    except service.PaymentError as exc:
        raise _error(exc) from None
    if created:
        response.status_code = status.HTTP_201_CREATED
        await _audit(db, auth, request, "payment.recorded", payment, payer=payer)
    return await _one(db, payment)


@router.get("/payments/{payment_id}", response_model=PaymentOut)
async def get_payment(payment_id: uuid.UUID, auth: CanView, db: DB) -> PaymentOut:
    return await _one(db, await _payment(db, auth, payment_id, Permission.PAYMENTS_VIEW))


@router.post("/payments/{payment_id}/allocations", response_model=PaymentOut)
async def allocate(
    payment_id: uuid.UUID, body: AllocationChange, auth: CanManage, request: Request, db: DB
) -> PaymentOut:
    p = await _payment(db, auth, payment_id, Permission.PAYMENTS_MANAGE)
    inv = await _invoice_of(db, p, body.invoice_id)
    try:
        await service.allocate(db, p, inv, body.amount, user_id=auth.user.id)
    except service.PaymentError as exc:
        raise _error(exc) from None
    await _audit(db, auth, request, "payment.allocated", p, invoice=inv.number, to=str(body.amount))
    return await _one(db, p)


@router.post("/payments/{payment_id}/release", response_model=PaymentOut)
async def release(
    payment_id: uuid.UUID, body: AllocationChange, auth: CanManage, request: Request, db: DB
) -> PaymentOut:
    p = await _payment(db, auth, payment_id, Permission.PAYMENTS_MANAGE)
    inv = await _invoice_of(db, p, body.invoice_id)
    try:
        await service.release(db, p, inv, body.amount, user_id=auth.user.id)
    except service.PaymentError as exc:
        raise _error(exc) from None
    await _audit(
        db, auth, request, "payment.released", p, invoice=inv.number, released=str(body.amount)
    )
    return await _one(db, p)


@router.post("/payments/{payment_id}/refunds", response_model=PaymentOut)
async def refund(
    payment_id: uuid.UUID,
    body: RefundCreate,
    auth: CanRefund,
    request: Request,
    response: Response,
    db: DB,
) -> PaymentOut:
    p = await _payment(db, auth, payment_id, Permission.PAYMENTS_REFUND)
    prop = await db.get(Property, p.property_id)
    assert prop is not None
    # A retried request returns the refund already recorded, before anything else runs.
    previous = await db.scalar(
        select(Refund).where(
            Refund.organisation_id == p.organisation_id,
            Refund.idempotency_key == body.idempotency_key,
        )
    )
    if previous is not None:
        if previous.payment_id != p.id or previous.amount != body.amount:
            raise HTTPException(
                status_code=409, detail="This refund was already recorded with different details."
            )
        return await _one(db, p)
    try:
        if body.release_from_invoice_id is not None:
            inv = await _invoice_of(db, p, body.release_from_invoice_id)
            # Only an overpayment may be released this way: the invoice must stay settled.
            over = -(await service.balance(db, inv))
            free = (await service.state(db, p.id)).unallocated(p)
            needed = body.amount - free
            if needed > ZERO:
                if needed > over:
                    raise service.PaymentError(
                        f"The invoice is only overpaid by {max(over, ZERO)}."
                    )
                await service.release(db, p, inv, needed, user_id=auth.user.id)
        row, created = await service.refund(
            db,
            p,
            amount=body.amount,
            method=body.method,
            reason=body.reason,
            reference=body.reference,
            refunded_on=_today(prop),
            idempotency_key=body.idempotency_key,
            user_id=auth.user.id,
        )
    except service.PaymentError as exc:
        raise _error(exc) from None
    if created:
        response.status_code = status.HTTP_201_CREATED
        await _audit(
            db, auth, request, "payment.refunded", p, refunded=str(row.amount), reason=row.reason
        )
    return await _one(db, p)


@router.post("/payments/{payment_id}/reverse", response_model=PaymentOut)
async def reverse(
    payment_id: uuid.UUID, body: ReverseRequest, auth: CanRefund, request: Request, db: DB
) -> PaymentOut:
    p = await _payment(db, auth, payment_id, Permission.PAYMENTS_REFUND)
    try:
        released = await service.reverse(db, p, reason=body.reason, user_id=auth.user.id)
    except service.PaymentError as exc:
        raise _error(exc) from None
    await _audit(db, auth, request, "payment.reversed", p, reason=body.reason, invoices=released)
    return await _one(db, p)


@router.get("/invoices/{invoice_id}/payments", response_model=InvoicePayments)
async def invoice_payments(invoice_id: uuid.UUID, auth: CanView, db: DB) -> InvoicePayments:
    inv = await db.get(Invoice, invoice_id)
    if inv is None:
        raise not_found("Invoice")
    auth.require_for_property(Permission.PAYMENTS_VIEW, inv.property_id)
    ids = (
        await db.scalars(
            select(PaymentAllocation.payment_id)
            .where(PaymentAllocation.invoice_id == inv.id)
            .distinct()
        )
    ).all()
    payments = (
        await db.scalars(select(Payment).where(Payment.id.in_(ids)).order_by(Payment.recorded_at))
    ).all()
    paid = await service.paid_total(db, inv.id)
    credited = await credited_total(db, inv.id)
    return InvoicePayments(
        invoice_id=inv.id,
        currency=inv.currency,
        total=inv.total,
        credited=credited,
        paid=paid,
        balance=await service.balance(db, inv),
        payments=await _out(db, list(payments)),
    )


@router.get("/properties/{property_id}/payments", response_model=list[PaymentOut])
async def list_payments(
    property_id: uuid.UUID,
    auth: CanView,
    db: DB,
    reservation_id: uuid.UUID | None = None,
    unallocated_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[PaymentOut]:
    prop = await get_property(db, property_id, auth, Permission.PAYMENTS_VIEW)
    stmt = select(Payment).where(Payment.property_id == prop.id)
    if reservation_id is not None:
        stmt = stmt.where(Payment.reservation_id == reservation_id)
    rows = (await db.scalars(stmt.order_by(Payment.recorded_at.desc()).limit(limit))).all()
    out = await _out(db, list(rows))
    return [p for p in out if p.unallocated > ZERO] if unallocated_only else out


@router.get("/properties/{property_id}/cash-up", response_model=CashUp)
async def cash_up(
    property_id: uuid.UUID,
    auth: CanView,
    db: DB,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> CashUp:
    """Money in and out per day and method: what the drawer and card machine should show.
    Reversed payments moved no money and are left out of the totals."""
    prop = await get_property(db, property_id, auth, Permission.PAYMENTS_VIEW)
    today = _today(prop)
    start = date_from or today
    end = date_to or start
    if end < start or (end - start).days >= MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"Choose a range of up to {MAX_DAYS} days.")
    payments = (
        await db.scalars(
            select(Payment)
            .where(
                Payment.property_id == prop.id,
                Payment.received_on >= start,
                Payment.received_on <= end,
            )
            .order_by(Payment.received_on, Payment.recorded_at)
        )
    ).all()
    refunds = (
        await db.scalars(
            select(Refund)
            .where(
                Refund.property_id == prop.id,
                Refund.refunded_on >= start,
                Refund.refunded_on <= end,
            )
            .order_by(Refund.refunded_on, Refund.recorded_at)
        )
    ).all()

    Key = tuple[str, str]
    per_day: dict[date, dict[Key, list[Decimal]]] = defaultdict(
        lambda: defaultdict(lambda: [ZERO, ZERO, ZERO])
    )
    for p in payments:
        if p.reversed_at is None:
            cell = per_day[p.received_on][(p.method, p.currency)]
            cell[0] += p.amount
            cell[2] += 1
    for r in refunds:
        per_day[r.refunded_on][(r.method, r.currency)][1] += r.amount

    def totals(cells: dict[Key, list[Decimal]]) -> list[MethodTotal]:
        return [
            MethodTotal(
                method=m,
                currency=c,
                received=v[0],
                refunded=v[1],
                net=v[0] - v[1],
                count=int(v[2]),
            )
            for (m, c), v in sorted(cells.items())
        ]

    overall: dict[Key, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO, ZERO])
    days = []
    d = start
    while d <= end:
        if d in per_day:
            for k, v in per_day[d].items():
                for i in range(3):
                    overall[k][i] += v[i]
            days.append(CashUpDay(date=d, totals=totals(per_day[d])))
        d += timedelta(days=1)
    return CashUp(
        property_id=prop.id,
        date_from=start,
        date_to=end,
        days=days,
        totals=totals(overall),
        payments=await _out(db, list(payments)),
        refunds=[RefundOut.model_validate(r) for r in refunds],
    )
