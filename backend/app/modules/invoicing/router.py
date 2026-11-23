"""Invoices and credit notes (ADR-0009)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app.core.errors import not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission_anywhere
from app.modules.auth.models import User
from app.modules.auth.permissions import Permission
from app.modules.guests.models import Guest
from app.modules.invoicing import service
from app.modules.invoicing.models import (
    CreditNote,
    CreditNoteItem,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
)
from app.modules.invoicing.schemas import (
    CreditCreate,
    CreditNoteItemOut,
    CreditNoteOut,
    ExtraCreate,
    InvoiceCreate,
    InvoiceOut,
    InvoiceSummary,
    InvoiceUpdate,
    ItemOut,
    Seller,
    TaxLine,
)
from app.modules.properties.models import Property
from app.modules.properties.router import get_property
from app.modules.rates.models import Tax
from app.modules.rates.pricing import TaxRate
from app.modules.reservations.models import Reservation

router = APIRouter(prefix="/api/v1", tags=["invoices"])

CanView = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.INVOICES_VIEW))]
CanManage = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.INVOICES_MANAGE))]
CanCredit = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.INVOICES_CREDIT))]
ZERO = Decimal("0.00")


def _error(exc: service.InvoiceError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


def _today(prop: Property) -> datetime:
    return datetime.now(ZoneInfo(prop.timezone))


async def _invoice(db: DB, auth: AuthContext, invoice_id: uuid.UUID, perm: Permission) -> Invoice:
    inv = await db.get(Invoice, invoice_id)
    if inv is None:
        raise not_found("Invoice")
    auth.require_for_property(perm, inv.property_id)
    return inv


async def _draft(db: DB, auth: AuthContext, invoice_id: uuid.UUID) -> Invoice:
    inv = await _invoice(db, auth, invoice_id, Permission.INVOICES_MANAGE)
    if inv.status != InvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=409, detail="Issued invoices cannot be changed. Use a credit note."
        )
    return inv


async def _credit_notes(db: DB, invoice: Invoice) -> list[CreditNoteOut]:
    rows = (
        await db.execute(
            select(CreditNote, User.full_name)
            .join(User, User.id == CreditNote.issued_by)
            .where(CreditNote.invoice_id == invoice.id)
            .order_by(CreditNote.issued_at)
        )
    ).all()
    out = []
    for note, name in rows:
        items = (
            await db.scalars(
                select(CreditNoteItem)
                .where(CreditNoteItem.credit_note_id == note.id)
                .order_by(CreditNoteItem.id)
            )
        ).all()
        out.append(
            CreditNoteOut(
                id=note.id,
                invoice_id=invoice.id,
                invoice_number=invoice.number or "",
                number=note.number,
                reason=note.reason,
                issue_date=note.issue_date,
                currency=note.currency,
                net_total=note.net_total,
                tax_total=note.tax_total,
                total=note.total,
                issued_by_name=name,
                items=[CreditNoteItemOut.model_validate(i) for i in items],
            )
        )
    return out


def _seller(prop: Property) -> Seller:
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
    return Seller(
        name=prop.name,
        legal_name=prop.legal_name,
        tax_number=prop.tax_number,
        address=address,
        phone=prop.phone,
        email=prop.email,
    )


async def _out(db: DB, inv: Invoice) -> InvoiceOut:
    prop = await db.get(Property, inv.property_id)
    assert prop is not None
    items = (
        await db.scalars(
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == inv.id)
            .order_by(InvoiceItem.position)
        )
    ).all()
    credited = await service.credited_by_item(db, [i.id for i in items])
    summary: dict[tuple[str, Decimal], Decimal] = {}
    for i in items:
        for t in i.taxes:
            key = (t["name"], Decimal(t["rate_percent"]))
            summary[key] = summary.get(key, ZERO) + Decimal(t["amount"])
    reference = (
        await db.scalar(select(Reservation.reference).where(Reservation.id == inv.reservation_id))
        if inv.reservation_id
        else None
    )
    issuer = (
        await db.scalar(select(User.full_name).where(User.id == inv.issued_by))
        if inv.issued_by
        else None
    )
    notes = await _credit_notes(db, inv)
    return InvoiceOut(
        id=inv.id,
        property_id=inv.property_id,
        number=inv.number,
        status=inv.status,
        bill_to_name=inv.bill_to_name,
        bill_to_details=inv.bill_to_details,
        notes=inv.notes,
        reservation_id=inv.reservation_id,
        reservation_reference=reference,
        currency=inv.currency,
        issue_date=inv.issue_date,
        due_date=inv.due_date,
        net_total=inv.net_total,
        tax_total=inv.tax_total,
        total=inv.total,
        credited=sum((n.total for n in notes), ZERO),
        tax_summary=[TaxLine(name=k[0], rate_percent=k[1], amount=v) for k, v in summary.items()],
        issued_by_name=issuer,
        seller=_seller(prop),
        created_at=inv.created_at,
        items=[
            ItemOut.model_validate(i).model_copy(
                update={"credited_amount": credited.get(i.id, (ZERO, ZERO, ZERO, {}))[2]}
            )
            for i in items
        ],
        credit_notes=notes,
    )


async def _record(
    db: DB, auth: AuthContext, request: Request, action: str, inv: Invoice, **data: object
) -> None:
    await audit.record(
        db,
        action=action,
        organisation_id=inv.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="invoice",
        entity_id=inv.id,
        data={"number": inv.number, "total": str(inv.total), **data},
        ip_address=client_ip(request),
    )


@router.get("/properties/{property_id}/invoices", response_model=list[InvoiceSummary])
async def list_invoices(
    property_id: uuid.UUID,
    auth: CanView,
    db: DB,
    status_filter: Annotated[
        Literal["draft", "issued", "discarded"] | None, Query(alias="status")
    ] = None,
    reservation_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[InvoiceSummary]:
    prop = await get_property(db, property_id, auth, Permission.INVOICES_VIEW)
    credited = (
        select(CreditNote.invoice_id, func.sum(CreditNote.total).label("credited"))
        .group_by(CreditNote.invoice_id)
        .subquery()
    )
    stmt = (
        select(Invoice, Reservation.reference, func.coalesce(credited.c.credited, ZERO))
        .outerjoin(Reservation, Reservation.id == Invoice.reservation_id)
        .outerjoin(credited, credited.c.invoice_id == Invoice.id)
        .where(Invoice.property_id == prop.id)
    )
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    else:
        stmt = stmt.where(Invoice.status != InvoiceStatus.DISCARDED)
    if reservation_id:
        stmt = stmt.where(Invoice.reservation_id == reservation_id)
    rows = await db.execute(
        stmt.order_by(Invoice.issued_at.desc().nulls_first(), Invoice.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        InvoiceSummary(
            id=inv.id,
            property_id=inv.property_id,
            number=inv.number,
            status=inv.status,
            bill_to_name=inv.bill_to_name,
            reservation_id=inv.reservation_id,
            reservation_reference=ref,
            currency=inv.currency,
            issue_date=inv.issue_date,
            due_date=inv.due_date,
            total=inv.total,
            credited=cr,
            created_at=inv.created_at,
        )
        for inv, ref, cr in rows.all()
    ]


@router.post(
    "/properties/{property_id}/invoices",
    response_model=InvoiceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    property_id: uuid.UUID, body: InvoiceCreate, auth: CanManage, request: Request, db: DB
) -> InvoiceOut:
    prop = await get_property(db, property_id, auth, Permission.INVOICES_MANAGE)
    reservation = None
    guest = None
    if body.reservation_id is not None:
        reservation = await db.get(Reservation, body.reservation_id)
        if reservation is None or reservation.property_id != prop.id:
            raise HTTPException(status_code=422, detail="Choose a booking of this property.")
        guest = await db.get(Guest, reservation.guest_id)
    bill_to = body.bill_to_name or (f"{guest.first_name} {guest.last_name}" if guest else None)
    if not bill_to:
        raise HTTPException(status_code=422, detail="Say who the invoice is for.")
    inv = Invoice(
        organisation_id=prop.organisation_id,
        property_id=prop.id,
        reservation_id=reservation.id if reservation else None,
        guest_id=guest.id if guest else None,
        currency=reservation.currency if reservation else prop.currency,
        bill_to_name=bill_to,
        bill_to_details=body.bill_to_details,
        notes=body.notes,
        created_by=auth.user.id,
    )
    db.add(inv)
    await db.flush()
    if reservation is not None:
        try:
            await service.add_reservation_rooms(db, inv, reservation)
        except service.InvoiceError as exc:
            raise _error(exc) from None
    await _record(db, auth, request, "invoice.drafted", inv, bill_to=bill_to)
    return await _out(db, inv)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(invoice_id: uuid.UUID, auth: CanView, db: DB) -> InvoiceOut:
    return await _out(db, await _invoice(db, auth, invoice_id, Permission.INVOICES_VIEW))


@router.patch("/invoices/{invoice_id}", response_model=InvoiceOut)
async def update_invoice(
    invoice_id: uuid.UUID, body: InvoiceUpdate, auth: CanManage, db: DB
) -> InvoiceOut:
    inv = await _draft(db, auth, invoice_id)
    changes = body.model_dump(exclude_unset=True)
    if "bill_to_name" in changes and not changes["bill_to_name"]:
        raise HTTPException(status_code=422, detail="Say who the invoice is for.")
    for k, v in changes.items():
        setattr(inv, k, v)
    await db.flush()
    return await _out(db, inv)


@router.post("/invoices/{invoice_id}/items", response_model=InvoiceOut, status_code=201)
async def add_item(invoice_id: uuid.UUID, body: ExtraCreate, auth: CanManage, db: DB) -> InvoiceOut:
    inv = await _draft(db, auth, invoice_id)
    taxes: list[TaxRate] = []
    if body.tax_ids:
        rows = (
            await db.scalars(
                select(Tax)
                .where(Tax.id.in_(body.tax_ids), Tax.property_id == inv.property_id)
                .order_by(Tax.sort_order, Tax.name)
            )
        ).all()
        if len(rows) != len(set(body.tax_ids)):
            raise HTTPException(status_code=422, detail="Choose taxes of this property.")
        taxes = [TaxRate(t.name, t.rate_percent) for t in rows]
    try:
        await service.add_extra(
            db,
            inv,
            description=body.description,
            quantity=body.quantity,
            unit_amount=body.unit_amount,
            include_tax=body.prices_include_tax,
            taxes=taxes,
            service_date=body.service_date,
        )
    except service.InvoiceError as exc:
        raise _error(exc) from None
    return await _out(db, inv)


@router.post("/invoices/{invoice_id}/reservation-rooms", response_model=InvoiceOut)
async def add_booking(
    invoice_id: uuid.UUID, auth: CanManage, db: DB, reservation_id: uuid.UUID
) -> InvoiceOut:
    inv = await _draft(db, auth, invoice_id)
    reservation = await db.get(Reservation, reservation_id)
    if reservation is None or reservation.property_id != inv.property_id:
        raise HTTPException(status_code=422, detail="Choose a booking of this property.")
    try:
        await service.add_reservation_rooms(db, inv, reservation)
    except service.InvoiceError as exc:
        raise _error(exc) from None
    if inv.reservation_id is None:
        inv.reservation_id = reservation.id
    return await _out(db, inv)


@router.delete("/invoices/{invoice_id}/items/{item_id}", response_model=InvoiceOut)
async def remove_item(
    invoice_id: uuid.UUID, item_id: uuid.UUID, auth: CanManage, db: DB
) -> InvoiceOut:
    inv = await _draft(db, auth, invoice_id)
    item = await db.get(InvoiceItem, item_id)
    if item is None or item.invoice_id != inv.id:
        raise not_found("Line")
    await db.delete(item)
    await db.flush()
    await service.recalculate(db, inv)
    return await _out(db, inv)


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceOut)
async def issue_invoice(
    invoice_id: uuid.UUID, auth: CanManage, request: Request, db: DB
) -> InvoiceOut:
    inv = await _draft(db, auth, invoice_id)
    prop = await db.get(Property, inv.property_id)
    assert prop is not None
    try:
        await service.issue(db, inv, today=_today(prop).date(), user_id=auth.user.id)
    except service.InvoiceError as exc:
        raise _error(exc) from None
    await _record(db, auth, request, "invoice.issued", inv, bill_to=inv.bill_to_name)
    return await _out(db, inv)


@router.post("/invoices/{invoice_id}/discard", response_model=InvoiceOut)
async def discard_invoice(
    invoice_id: uuid.UUID, auth: CanManage, request: Request, db: DB
) -> InvoiceOut:
    inv = await _draft(db, auth, invoice_id)
    inv.status = InvoiceStatus.DISCARDED
    await db.flush()
    await _record(db, auth, request, "invoice.discarded", inv)
    return await _out(db, inv)


@router.post("/invoices/{invoice_id}/credit-notes", response_model=CreditNoteOut, status_code=201)
async def credit_invoice(
    invoice_id: uuid.UUID, body: CreditCreate, auth: CanCredit, request: Request, db: DB
) -> CreditNoteOut:
    inv = await _invoice(db, auth, invoice_id, Permission.INVOICES_CREDIT)
    prop = await db.get(Property, inv.property_id)
    assert prop is not None
    try:
        note = await service.credit(
            db,
            inv,
            reason=body.reason,
            lines=[(line.invoice_item_id, line.amount) for line in body.lines],
            today=_today(prop).date(),
            user_id=auth.user.id,
        )
    except service.InvoiceError as exc:
        raise _error(exc) from None
    await audit.record(
        db,
        action="invoice.credited",
        organisation_id=inv.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="credit_note",
        entity_id=note.id,
        data={"number": note.number, "invoice": inv.number, "total": str(note.total)},
        ip_address=client_ip(request),
    )
    return next(n for n in await _credit_notes(db, inv) if n.id == note.id)
