"""Point of sale API (ADR-0015)."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, Auth, client_ip
from app.modules.auth.models import User
from app.modules.auth.permissions import Permission
from app.modules.guests.models import Guest
from app.modules.invoicing.models import Invoice
from app.modules.payments.models import PaymentMethod
from app.modules.pos import service
from app.modules.pos.models import PosOrder, PosOrderItem, PosOutlet, Service, Settlement
from app.modules.properties.models import Property
from app.modules.properties.router import get_property
from app.modules.rates.models import Tax
from app.modules.reservations.models import Reservation, ReservationRoom, ReservationStatus
from app.modules.rooms.models import Room

router = APIRouter(prefix="/api/v1", tags=["point of sale"])
Key = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
Price = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class OutletIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=100)


class OutletUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=2, max_length=100)
    status: Literal["active", "archived"] | None = None


class OutletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    status: str


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    outlet_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    category: str | None = Field(default=None, max_length=60)
    price: Price
    prices_include_tax: bool = True
    tax_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    sort_order: int = Field(default=0, ge=0, le=10_000)


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    category: str | None = Field(default=None, max_length=60)
    price: Price | None = None
    prices_include_tax: bool | None = None
    tax_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    status: Literal["active", "archived"] | None = None


class ItemOut(BaseModel):
    id: uuid.UUID
    outlet_id: uuid.UUID
    name: str
    category: str | None
    price: Decimal
    prices_include_tax: bool
    tax_ids: list[uuid.UUID]
    sort_order: int
    status: str


class SaleLine(BaseModel):
    service_id: uuid.UUID
    quantity: Annotated[Decimal, Field(gt=0, le=1000, max_digits=10, decimal_places=2)] = Decimal(1)


class SaleIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    outlet_id: uuid.UUID
    lines: list[SaleLine] = Field(min_length=1, max_length=100)
    settlement: Settlement
    reservation_id: uuid.UUID | None = None
    method: PaymentMethod | None = None
    payer_name: str | None = Field(default=None, min_length=2, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    idempotency_key: Key


class SaleItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    quantity: Decimal
    unit_amount: Decimal
    total: Decimal


class SaleOut(BaseModel):
    id: uuid.UUID
    outlet: str
    settlement: str
    reservation_reference: str | None
    room_label: str | None
    invoice_id: uuid.UUID
    invoice_number: str | None
    currency: str
    total: Decimal
    items: list[SaleItemOut]
    sold_by: str
    created_at: datetime


class InHouse(BaseModel):
    reservation_id: uuid.UUID
    reference: str
    guest_name: str
    rooms: list[str]
    check_out: date


def _item_out(s: Service) -> ItemOut:
    return ItemOut(
        id=s.id,
        outlet_id=s.outlet_id,
        name=s.name,
        category=s.category,
        price=s.price,
        prices_include_tax=s.prices_include_tax,
        tax_ids=[uuid.UUID(t) for t in s.tax_ids],
        sort_order=s.sort_order,
        status=s.status,
    )


async def _check_taxes(db: DB, prop: Property, tax_ids: list[uuid.UUID]) -> list[str]:
    if not tax_ids:
        return []
    found = (
        await db.scalars(select(Tax.id).where(Tax.id.in_(tax_ids), Tax.property_id == prop.id))
    ).all()
    if len(set(found)) != len(set(tax_ids)):
        raise HTTPException(status_code=422, detail="Choose taxes of this property.")
    return [str(t) for t in dict.fromkeys(tax_ids)]


async def _outlet(db: DB, prop: Property, outlet_id: uuid.UUID) -> PosOutlet:
    outlet = await db.get(PosOutlet, outlet_id)
    if outlet is None or outlet.property_id != prop.id:
        raise HTTPException(status_code=422, detail="Choose an outlet of this property.")
    return outlet


# --- catalogue -----------------------------------------------------------------------------


@router.get("/properties/{property_id}/pos/outlets", response_model=list[OutletOut])
async def list_outlets(property_id: uuid.UUID, auth: Auth, db: DB) -> list[PosOutlet]:
    prop = await get_property(db, property_id, auth, Permission.POS_SELL)
    rows = await db.scalars(
        select(PosOutlet)
        .where(PosOutlet.property_id == prop.id)
        .order_by(PosOutlet.status, PosOutlet.name)
    )
    return list(rows.all())


@router.post("/properties/{property_id}/pos/outlets", response_model=OutletOut, status_code=201)
async def create_outlet(property_id: uuid.UUID, body: OutletIn, auth: Auth, db: DB) -> PosOutlet:
    prop = await get_property(db, property_id, auth, Permission.POS_MANAGE)
    outlet = PosOutlet(organisation_id=prop.organisation_id, property_id=prop.id, name=body.name)
    db.add(outlet)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise HTTPException(status_code=409, detail="An outlet with that name exists.") from None
    return outlet


@router.patch("/pos/outlets/{outlet_id}", response_model=OutletOut)
async def update_outlet(outlet_id: uuid.UUID, body: OutletUpdate, auth: Auth, db: DB) -> PosOutlet:
    outlet = await db.get(PosOutlet, outlet_id)
    if outlet is None:
        raise not_found("Outlet")
    auth.require_for_property(Permission.POS_MANAGE, outlet.property_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(outlet, k, v)
    await db.flush()
    return outlet


@router.get("/properties/{property_id}/pos/items", response_model=list[ItemOut])
async def list_items(property_id: uuid.UUID, auth: Auth, db: DB) -> list[ItemOut]:
    prop = await get_property(db, property_id, auth, Permission.POS_SELL)
    rows = await db.scalars(
        select(Service)
        .where(Service.property_id == prop.id)
        .order_by(Service.status, Service.category, Service.sort_order, Service.name)
    )
    return [_item_out(s) for s in rows.all()]


@router.post("/properties/{property_id}/pos/items", response_model=ItemOut, status_code=201)
async def create_item(property_id: uuid.UUID, body: ItemIn, auth: Auth, db: DB) -> ItemOut:
    prop = await get_property(db, property_id, auth, Permission.POS_MANAGE)
    outlet = await _outlet(db, prop, body.outlet_id)
    item = Service(
        organisation_id=prop.organisation_id,
        property_id=prop.id,
        outlet_id=outlet.id,
        name=body.name,
        category=body.category,
        price=body.price,
        prices_include_tax=body.prices_include_tax,
        tax_ids=await _check_taxes(db, prop, body.tax_ids),
        sort_order=body.sort_order,
    )
    db.add(item)
    await db.flush()
    return _item_out(item)


@router.patch("/pos/items/{item_id}", response_model=ItemOut)
async def update_item(item_id: uuid.UUID, body: ItemUpdate, auth: Auth, db: DB) -> ItemOut:
    item = await db.get(Service, item_id)
    if item is None:
        raise not_found("Item")
    auth.require_for_property(Permission.POS_MANAGE, item.property_id)
    prop = await db.get(Property, item.property_id)
    assert prop is not None
    changes = body.model_dump(exclude_unset=True)
    if "tax_ids" in changes and changes["tax_ids"] is not None:
        changes["tax_ids"] = await _check_taxes(db, prop, changes["tax_ids"])
    for k, v in changes.items():
        if v is not None or k == "category":
            setattr(item, k, v)
    await db.flush()
    return _item_out(item)


# --- selling -------------------------------------------------------------------------------


@router.get("/properties/{property_id}/pos/in-house", response_model=list[InHouse])
async def in_house(property_id: uuid.UUID, auth: Auth, db: DB) -> list[InHouse]:
    """Checked-in guests who can charge to their room, by room number."""
    prop = await get_property(db, property_id, auth, Permission.POS_SELL)
    rows = (
        await db.execute(
            select(Reservation, Guest.first_name, Guest.last_name)
            .join(Guest, Guest.id == Reservation.guest_id)
            .where(
                Reservation.property_id == prop.id,
                Reservation.status == ReservationStatus.CHECKED_IN,
            )
        )
    ).all()
    out = []
    for r, first, last in rows:
        numbers = (
            await db.scalars(
                select(Room.number)
                .join(ReservationRoom, ReservationRoom.room_id == Room.id)
                .where(ReservationRoom.reservation_id == r.id)
                .order_by(Room.number)
            )
        ).all()
        out.append(
            InHouse(
                reservation_id=r.id,
                reference=r.reference,
                guest_name=f"{first} {last}",
                rooms=list(numbers),
                check_out=r.check_out,
            )
        )
    return sorted(out, key=lambda x: (x.rooms[0] if x.rooms else "~", x.guest_name))


async def _sale_out(db: DB, orders: list[PosOrder]) -> list[SaleOut]:
    out = []
    for o in orders:
        outlet = await db.get(PosOutlet, o.outlet_id)
        invoice = await db.get(Invoice, o.invoice_id)
        seller = await db.scalar(select(User.full_name).where(User.id == o.created_by))
        reference = None
        room_label = None
        if o.reservation_id:
            r = await db.get(Reservation, o.reservation_id)
            reference = r.reference if r else None
            numbers = (
                await db.scalars(
                    select(Room.number)
                    .join(ReservationRoom, ReservationRoom.room_id == Room.id)
                    .where(ReservationRoom.reservation_id == o.reservation_id)
                    .order_by(Room.number)
                )
            ).all()
            room_label = ", ".join(numbers) or None
        items = (
            await db.scalars(
                select(PosOrderItem).where(PosOrderItem.order_id == o.id).order_by(PosOrderItem.position)
            )
        ).all()
        out.append(
            SaleOut(
                id=o.id,
                outlet=outlet.name if outlet else "",
                settlement=o.settlement,
                reservation_reference=reference,
                room_label=room_label,
                invoice_id=o.invoice_id,
                invoice_number=invoice.number if invoice else None,
                currency=o.currency,
                total=o.total,
                items=[SaleItemOut.model_validate(i) for i in items],
                sold_by=seller or "",
                created_at=o.created_at,
            )
        )
    return out


@router.post("/properties/{property_id}/pos/sales", response_model=SaleOut)
async def ring_up(
    property_id: uuid.UUID, body: SaleIn, auth: Auth, request: Request, response: Response, db: DB
) -> SaleOut:
    prop = await get_property(db, property_id, auth, Permission.POS_SELL)
    outlet = await _outlet(db, prop, body.outlet_id)
    reservation = await db.get(Reservation, body.reservation_id) if body.reservation_id else None
    today = datetime.now(ZoneInfo(prop.timezone)).date()
    try:
        order, created = await service.sell(
            db,
            prop=prop,
            outlet=outlet,
            lines=[service.Line(line.service_id, line.quantity) for line in body.lines],
            settlement=body.settlement,
            reservation=reservation,
            method=body.method,
            payer_name=body.payer_name,
            note=body.note,
            today=today,
            idempotency_key=body.idempotency_key,
            user_id=auth.user.id,
        )
    except service.SaleError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
    if created:
        response.status_code = status.HTTP_201_CREATED
        await audit.record(
            db,
            action="pos.sale",
            organisation_id=prop.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="pos_order",
            entity_id=order.id,
            data={"outlet": outlet.name, "settlement": order.settlement, "total": str(order.total)},
            ip_address=client_ip(request),
        )
    return (await _sale_out(db, [order]))[0]


@router.get("/properties/{property_id}/pos/sales", response_model=list[SaleOut])
async def list_sales(
    property_id: uuid.UUID, auth: Auth, db: DB, day: date | None = None
) -> list[SaleOut]:
    prop = await get_property(db, property_id, auth, Permission.POS_SELL)
    zone = ZoneInfo(prop.timezone)
    d = day or datetime.now(zone).date()
    start = datetime.combine(d, time.min, zone).astimezone(UTC)
    rows = await db.scalars(
        select(PosOrder)
        .where(
            PosOrder.property_id == prop.id,
            PosOrder.created_at >= start,
            PosOrder.created_at < start + timedelta(days=1),
        )
        .order_by(PosOrder.created_at.desc())
        .limit(500)
    )
    return await _sale_out(db, list(rows.all()))
