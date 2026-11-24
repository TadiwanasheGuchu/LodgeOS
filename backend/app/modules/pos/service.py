"""Ringing up a sale (ADR-0015). Money goes through invoicing and payments."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.guests.models import Guest
from app.modules.invoicing import service as invoicing
from app.modules.invoicing.models import Invoice, InvoiceStatus
from app.modules.payments import service as payments
from app.modules.pos.models import PosOrder, PosOrderItem, PosOutlet, Service, Settlement
from app.modules.properties.models import Property, RecordStatus
from app.modules.rates.models import Tax
from app.modules.rates.pricing import TaxRate, cents
from app.modules.reservations.models import Reservation, ReservationStatus

ZERO = Decimal("0.00")


class SaleError(ValueError):
    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Line:
    service_id: uuid.UUID
    quantity: Decimal


async def _folio(db: AsyncSession, reservation: Reservation, *, user_id: uuid.UUID) -> Invoice:
    """The booking's draft invoice, created (with its rooms) when there is none."""
    # One folio per booking at a time: serialise on the reservation row.
    await db.execute(
        select(Reservation.id).where(Reservation.id == reservation.id).with_for_update()
    )
    folio = await db.scalar(
        select(Invoice)
        .where(Invoice.reservation_id == reservation.id, Invoice.status == InvoiceStatus.DRAFT)
        .order_by(Invoice.created_at)
        .limit(1)
    )
    if folio is not None:
        return folio
    guest = await db.get(Guest, reservation.guest_id)
    assert guest is not None
    folio = Invoice(
        organisation_id=reservation.organisation_id,
        property_id=reservation.property_id,
        reservation_id=reservation.id,
        guest_id=guest.id,
        currency=reservation.currency,
        bill_to_name=f"{guest.first_name} {guest.last_name}",
        created_by=user_id,
    )
    db.add(folio)
    await db.flush()
    try:
        await invoicing.add_reservation_rooms(db, folio, reservation)
    except invoicing.InvoiceError:
        pass  # the stay is already invoiced elsewhere; the folio carries the extras only
    return folio


async def sell(
    db: AsyncSession,
    *,
    prop: Property,
    outlet: PosOutlet,
    lines: list[Line],
    settlement: Settlement,
    reservation: Reservation | None,
    method: str | None,
    payer_name: str | None,
    note: str | None,
    today: date,
    idempotency_key: str,
    user_id: uuid.UUID,
) -> tuple[PosOrder, bool]:
    existing = await db.scalar(
        select(PosOrder).where(
            PosOrder.organisation_id == prop.organisation_id,
            PosOrder.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing, False
    if outlet.status != RecordStatus.ACTIVE:
        raise SaleError("This outlet is closed.")
    if not lines:
        raise SaleError("Add at least one item.", 422)

    services = {
        s.id: s
        for s in (
            await db.scalars(
                select(Service).where(
                    Service.id.in_([line.service_id for line in lines]),
                    Service.outlet_id == outlet.id,
                    Service.status == RecordStatus.ACTIVE,
                )
            )
        ).all()
    }
    if len(services) != len({line.service_id for line in lines}):
        raise SaleError("Choose items sold at this outlet.", 422)
    taxes = {
        str(t.id): t
        for t in (
            await db.scalars(
                select(Tax).where(Tax.property_id == prop.id, Tax.status == RecordStatus.ACTIVE)
            )
        ).all()
    }

    if settlement == Settlement.ROOM:
        if reservation is None or reservation.property_id != prop.id:
            raise SaleError("Choose a booking of this property.", 422)
        if reservation.status != ReservationStatus.CHECKED_IN:
            raise SaleError("Only guests who are checked in can charge to their room.")
        invoice = await _folio(db, reservation, user_id=user_id)
    else:
        if method is None:
            raise SaleError("Choose how the guest paid.", 422)
        invoice = Invoice(
            organisation_id=prop.organisation_id,
            property_id=prop.id,
            currency=prop.currency,
            bill_to_name=payer_name or "Walk-in guest",
            created_by=user_id,
        )
        db.add(invoice)
        await db.flush()

    order = PosOrder(
        organisation_id=prop.organisation_id,
        property_id=prop.id,
        outlet_id=outlet.id,
        settlement=settlement,
        reservation_id=reservation.id if settlement == Settlement.ROOM and reservation else None,
        invoice_id=invoice.id,
        currency=invoice.currency,
        total=ZERO,
        note=note,
        idempotency_key=idempotency_key,
        created_by=user_id,
        created_at=datetime.now(UTC),
    )
    total = ZERO
    items = []
    for line in lines:
        s = services[line.service_id]
        item = await invoicing.add_extra(
            db,
            invoice,
            description=f"{outlet.name}: {s.name}",
            quantity=line.quantity,
            unit_amount=s.price,
            include_tax=s.prices_include_tax,
            taxes=[TaxRate(taxes[t].name, taxes[t].rate_percent) for t in s.tax_ids if t in taxes],
            service_date=today,
        )
        total += item.total_amount
        items.append((s, line.quantity, item.total_amount))
    order.total = cents(total)

    if settlement == Settlement.PAID:
        await invoicing.issue(db, invoice, today=today, user_id=user_id)
        payment, _ = await payments.record(
            db,
            {
                "organisation_id": prop.organisation_id,
                "property_id": prop.id,
                "reservation_id": reservation.id if reservation else None,
                "method": method,
                "currency": invoice.currency,
                "amount": invoice.total,
                "received_on": today,
                "payer_name": invoice.bill_to_name,
                "reference": None,
                "note": f"{outlet.name} sale",
                "idempotency_key": f"pos-{idempotency_key}"[:64],
                "recorded_by": user_id,
            },
        )
        await payments.allocate(db, payment, invoice, invoice.total, user_id=user_id)
        order.payment_id = payment.id

    db.add(order)
    await db.flush()
    for position, (s, qty, line_total) in enumerate(items, start=1):
        db.add(
            PosOrderItem(
                organisation_id=prop.organisation_id,
                order_id=order.id,
                position=position,
                service_id=s.id,
                name=s.name,
                quantity=qty,
                unit_amount=s.price,
                total=line_total,
            )
        )
    await db.flush()
    return order, True
