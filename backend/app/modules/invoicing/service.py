"""Invoice and credit-note rules (ADR-0009). Callers hold the transaction."""

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.invoicing.models import (
    PREFIX,
    CreditNote,
    CreditNoteItem,
    DocumentKind,
    DocumentSequence,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    ItemKind,
)
from app.modules.rates.pricing import TaxAmount, TaxRate, cents, split_taxes
from app.modules.reservations.models import Reservation, ReservationRoom, ReservationStatus

ZERO = Decimal("0.00")
LIVE = (InvoiceStatus.DRAFT, InvoiceStatus.ISSUED)


class InvoiceError(ValueError):
    """A rule was broken; the message is shown to staff."""

    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


def _tax_json(taxes: Sequence[TaxAmount]) -> list[dict[str, Any]]:
    return [
        {"name": t.name, "rate_percent": str(t.rate_percent), "amount": str(t.amount)}
        for t in taxes
    ]


async def next_number(db: AsyncSession, organisation_id: uuid.UUID, kind: DocumentKind) -> str:
    """Take the next gapless number. The row lock is held until the transaction ends, so a
    rolled-back issue gives its number back."""
    await db.execute(
        insert(DocumentSequence)
        .values(organisation_id=organisation_id, kind=kind, next_number=1)
        .on_conflict_do_nothing()
    )
    seq = await db.scalar(
        select(DocumentSequence)
        .where(DocumentSequence.organisation_id == organisation_id, DocumentSequence.kind == kind)
        .with_for_update()
    )
    assert seq is not None
    n = seq.next_number
    seq.next_number = n + 1
    return f"{PREFIX[kind]}-{n:06d}"


async def recalculate(db: AsyncSession, invoice: Invoice) -> None:
    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(InvoiceItem.net_amount), ZERO),
                func.coalesce(func.sum(InvoiceItem.tax_amount), ZERO),
                func.coalesce(func.sum(InvoiceItem.total_amount), ZERO),
            ).where(InvoiceItem.invoice_id == invoice.id)
        )
    ).one()
    invoice.net_total, invoice.tax_total, invoice.total = row[0], row[1], row[2]


async def _next_position(db: AsyncSession, invoice: Invoice) -> int:
    current = await db.scalar(
        select(func.max(InvoiceItem.position)).where(InvoiceItem.invoice_id == invoice.id)
    )
    return (current or 0) + 1


async def credited_by_item(
    db: AsyncSession, item_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[Decimal, Decimal, Decimal, dict[str, Decimal]]]:
    """Per invoice line: credited net, tax, total and per-tax amounts so far."""
    out: dict[uuid.UUID, tuple[Decimal, Decimal, Decimal, dict[str, Decimal]]] = {}
    if not item_ids:
        return out
    rows = await db.scalars(
        select(CreditNoteItem).where(CreditNoteItem.invoice_item_id.in_(item_ids))
    )
    for c in rows.all():
        net, tax, total, per = out.get(c.invoice_item_id, (ZERO, ZERO, ZERO, {}))
        per = dict(per)
        for t in c.taxes:
            per[t["name"]] = per.get(t["name"], ZERO) + Decimal(t["amount"])
        out[c.invoice_item_id] = (
            net + c.net_amount,
            tax + c.tax_amount,
            total + c.total_amount,
            per,
        )
    return out


async def invoiced_rooms(db: AsyncSession, reservation_id: uuid.UUID) -> set[uuid.UUID]:
    """Booked rooms already on a live invoice and not fully credited back."""
    items = (
        await db.execute(
            select(InvoiceItem.id, InvoiceItem.reservation_room_id, InvoiceItem.total_amount)
            .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
            .join(ReservationRoom, ReservationRoom.id == InvoiceItem.reservation_room_id)
            .where(
                ReservationRoom.reservation_id == reservation_id,
                Invoice.status.in_(LIVE),
            )
        )
    ).all()
    credited = await credited_by_item(db, [i[0] for i in items])
    return {
        rr_id
        for item_id, rr_id, total in items
        if rr_id is not None and credited.get(item_id, (ZERO, ZERO, ZERO, {}))[2] < total
    }


def _stay_description(snapshot: dict[str, Any], check_in: date, check_out: date) -> str:
    nights = (check_out - check_in).days
    span = f"{check_in:%d %b} to {check_out:%d %b %Y}"
    return (
        f"{snapshot['room_type']} · {snapshot['rate_plan']} · {span}"
        f" ({nights} night{'s' if nights != 1 else ''})"
    )


async def add_reservation_rooms(
    db: AsyncSession, invoice: Invoice, reservation: Reservation
) -> int:
    """Copy the booking's uninvoiced rooms onto the draft, exactly as priced at booking."""
    # Serialise invoicing of one booking so a room cannot land on two invoices.
    await db.execute(
        select(Reservation.id).where(Reservation.id == reservation.id).with_for_update()
    )
    if reservation.currency != invoice.currency:
        raise InvoiceError("The booking is in a different currency from this invoice.")
    if reservation.status in (ReservationStatus.CANCELLED, ReservationStatus.NO_SHOW):
        raise InvoiceError("Cancelled and no-show bookings are not invoiced for their stay.")
    taken = await invoiced_rooms(db, reservation.id)
    rooms = (
        await db.scalars(
            select(ReservationRoom)
            .where(ReservationRoom.reservation_id == reservation.id)
            .order_by(ReservationRoom.check_in, ReservationRoom.id)
        )
    ).all()
    position = await _next_position(db, invoice)
    added = 0
    for rr in rooms:
        if rr.id in taken:
            continue
        snap = rr.price_snapshot
        db.add(
            InvoiceItem(
                organisation_id=invoice.organisation_id,
                invoice_id=invoice.id,
                position=position,
                kind=ItemKind.ACCOMMODATION,
                description=_stay_description(snap, rr.check_in, rr.check_out),
                quantity=Decimal("1.00"),
                unit_amount=rr.total_amount,
                prices_include_tax=True,
                net_amount=Decimal(snap["net_total"]),
                tax_amount=rr.tax_amount,
                total_amount=rr.total_amount,
                taxes=snap["taxes"],
                reservation_room_id=rr.id,
                service_from=rr.check_in,
                service_to=rr.check_out,
            )
        )
        position += 1
        added += 1
    if added == 0:
        raise InvoiceError("Every room of this booking is already on an invoice.")
    await db.flush()
    await recalculate(db, invoice)
    return added


async def add_extra(
    db: AsyncSession,
    invoice: Invoice,
    *,
    description: str,
    quantity: Decimal,
    unit_amount: Decimal,
    include_tax: bool,
    taxes: Sequence[TaxRate],
    service_date: date | None,
) -> InvoiceItem:
    gross_or_net = cents(quantity * unit_amount)
    if gross_or_net <= ZERO:
        raise InvoiceError("The line must be more than zero.", 422)
    net, tax_amounts, total = split_taxes(gross_or_net, taxes, include_tax=include_tax)
    item = InvoiceItem(
        organisation_id=invoice.organisation_id,
        invoice_id=invoice.id,
        position=await _next_position(db, invoice),
        kind=ItemKind.EXTRA,
        description=description,
        quantity=quantity,
        unit_amount=unit_amount,
        prices_include_tax=include_tax,
        net_amount=net,
        tax_amount=total - net,
        total_amount=total,
        taxes=_tax_json(tax_amounts),
        service_from=service_date,
        service_to=service_date,
    )
    db.add(item)
    await db.flush()
    await recalculate(db, invoice)
    return item


async def issue(db: AsyncSession, invoice: Invoice, *, today: date, user_id: uuid.UUID) -> None:
    if invoice.status != InvoiceStatus.DRAFT:
        raise InvoiceError("Only a draft can be issued.")
    await recalculate(db, invoice)
    if invoice.total <= ZERO:
        raise InvoiceError("Add at least one line before issuing.")
    invoice.number = await next_number(db, invoice.organisation_id, DocumentKind.INVOICE)
    invoice.issue_date = today
    if invoice.due_date is None or invoice.due_date < today:
        invoice.due_date = today
    invoice.issued_at = datetime.now(UTC)
    invoice.issued_by = user_id
    invoice.status = InvoiceStatus.ISSUED
    await db.flush()


def _split_credit(
    item: InvoiceItem,
    amount: Decimal,
    already: tuple[Decimal, Decimal, Decimal, dict[str, Decimal]],
) -> tuple[Decimal, list[TaxAmount], Decimal]:
    """Net, taxes and gross for crediting ``amount`` of a line."""
    c_net, _, c_total, c_per = already
    remaining = item.total_amount - c_total
    rates = [TaxRate(t["name"], Decimal(t["rate_percent"])) for t in item.taxes]
    if amount == remaining:
        # The whole remainder: take exactly what is left, so the line nets to zero.
        taxes = [
            TaxAmount(r.name, r.rate_percent, Decimal(t["amount"]) - c_per.get(r.name, ZERO))
            for r, t in zip(rates, item.taxes, strict=True)
        ]
        return item.net_amount - c_net, taxes, remaining
    net, taxes, total = split_taxes(amount, rates, include_tax=True)
    for t, original in zip(taxes, item.taxes, strict=True):
        if t.amount > Decimal(original["amount"]) - c_per.get(t.name, ZERO):
            raise InvoiceError("Credit the rest of this line in full instead.")
    return net, taxes, total


async def credit(
    db: AsyncSession,
    invoice: Invoice,
    *,
    reason: str,
    lines: Sequence[tuple[uuid.UUID, Decimal | None]],
    today: date,
    user_id: uuid.UUID,
) -> CreditNote:
    """Credit chosen lines of an issued invoice; ``None`` credits a line's whole remainder."""
    # Lock the invoice so two credit notes cannot over-credit the same line.
    await db.execute(select(Invoice.id).where(Invoice.id == invoice.id).with_for_update())
    if invoice.status != InvoiceStatus.ISSUED:
        raise InvoiceError("Only issued invoices can be credited.")
    items = {
        i.id: i
        for i in (
            await db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id))
        ).all()
    }
    already = await credited_by_item(db, list(items))
    if not lines or len({line_id for line_id, _ in lines}) != len(lines):
        raise InvoiceError("Choose each line to credit once.", 422)
    note = CreditNote(
        organisation_id=invoice.organisation_id,
        property_id=invoice.property_id,
        invoice_id=invoice.id,
        number="",
        reason=reason,
        issue_date=today,
        currency=invoice.currency,
        net_total=ZERO,
        tax_total=ZERO,
        total=ZERO,
        issued_at=datetime.now(UTC),
        issued_by=user_id,
    )
    parts: list[CreditNoteItem] = []
    for item_id, amount in lines:
        item = items.get(item_id)
        if item is None:
            raise InvoiceError("Choose lines of this invoice.", 422)
        so_far = already.get(item.id, (ZERO, ZERO, ZERO, {}))
        remaining = item.total_amount - so_far[2]
        if remaining <= ZERO:
            raise InvoiceError(f"“{item.description}” is already fully credited.")
        amount = remaining if amount is None else cents(amount)
        if amount <= ZERO or amount > remaining:
            raise InvoiceError(f"Credit between 0.01 and {remaining} on “{item.description}”.", 422)
        net, taxes, total = _split_credit(item, amount, so_far)
        parts.append(
            CreditNoteItem(
                organisation_id=invoice.organisation_id,
                invoice_item_id=item.id,
                description=item.description,
                net_amount=net,
                tax_amount=total - net,
                total_amount=total,
                taxes=_tax_json(taxes),
            )
        )
    note.net_total = sum((p.net_amount for p in parts), ZERO)
    note.tax_total = sum((p.tax_amount for p in parts), ZERO)
    note.total = sum((p.total_amount for p in parts), ZERO)
    note.number = await next_number(db, invoice.organisation_id, DocumentKind.CREDIT_NOTE)
    db.add(note)
    await db.flush()
    for p in parts:
        p.credit_note_id = note.id
        db.add(p)
    await db.flush()
    return note


async def credited_total(db: AsyncSession, invoice_id: uuid.UUID) -> Decimal:
    value = await db.scalar(
        select(func.coalesce(func.sum(CreditNote.total), ZERO)).where(
            CreditNote.invoice_id == invoice_id
        )
    )
    return value if value is not None else ZERO
