"""Taxes, rate plans, prices, seasons and price quotes for a property."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import conflict_from_integrity, not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission_anywhere
from app.modules.auth.permissions import Permission
from app.modules.properties.models import Property
from app.modules.properties.router import get_property
from app.modules.rates import pricing
from app.modules.rates.models import RatePlan, RatePlanPrice, SeasonalRate, Tax
from app.modules.rates.schemas import (
    NightOut,
    PriceFields,
    PriceOut,
    QuoteOut,
    QuoteRequest,
    RatePlanCreate,
    RatePlanDetail,
    RatePlanOut,
    RatePlanUpdate,
    SeasonCreate,
    SeasonOut,
    SeasonUpdate,
    TaxAmountOut,
    TaxCreate,
    TaxOut,
    TaxUpdate,
)
from app.modules.rates.service import price_stay
from app.modules.rooms.models import RoomType

router = APIRouter(prefix="/api/v1", tags=["rates"])

CanView = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.RATES_VIEW))]
CanManage = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.RATES_MANAGE))]

TAX_CONFLICTS = {"uq_taxes_property_id_name": "This property already has a tax with that name."}
PLAN_CONFLICTS = {
    "uq_rate_plans_property_id_code": "Another rate plan at this property uses that code.",
    "uq_rate_plans_property_id_name": "Another rate plan at this property has that name.",
}
SEASON_CONFLICTS = {
    "ex_seasonal_rates_no_overlap": (
        "These dates overlap another season for this room type in this rate plan."
    ),
}


ENTITY_TYPES: dict[type, str] = {Tax: "tax", RatePlan: "rate_plan", SeasonalRate: "season"}


async def _flush(db: DB, conflicts: dict[str, str]) -> None:
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise conflict_from_integrity(exc, conflicts) from None


async def _audit(
    db: DB, auth: AuthContext, request: Request, action: str, entity: Any, data: dict[str, Any]
) -> None:
    await audit.record(
        db,
        action=action,
        organisation_id=entity.organisation_id,
        actor_user_id=auth.user.id,
        entity_type=ENTITY_TYPES[type(entity)],
        entity_id=entity.id,
        data=data,
        ip_address=client_ip(request),
    )


def _reject_nulls(changes: dict[str, Any], nullable: set[str]) -> None:
    for key, value in changes.items():
        if value is None and key not in nullable:
            raise HTTPException(status_code=422, detail=f"{key} cannot be empty.")


async def _plan(db: DB, auth: AuthContext, plan_id: uuid.UUID, perm: Permission) -> RatePlan:
    plan = await db.get(RatePlan, plan_id)
    if plan is None:
        raise not_found("Rate plan")
    auth.require_for_property(perm, plan.property_id)
    return plan


async def _room_type_of(db: DB, property_id: uuid.UUID, room_type_id: uuid.UUID) -> RoomType:
    rt = await db.get(RoomType, room_type_id)
    if rt is None or rt.property_id != property_id:
        raise HTTPException(status_code=422, detail="Choose a room type from this property.")
    return rt


# --- taxes ------------------------------------------------------------------------------


@router.get("/properties/{property_id}/taxes", response_model=list[TaxOut])
async def list_taxes(property_id: uuid.UUID, auth: CanView, db: DB) -> list[Tax]:
    await get_property(db, property_id, auth, Permission.RATES_VIEW)
    rows = await db.scalars(
        select(Tax)
        .where(Tax.property_id == property_id)
        .order_by(Tax.status, Tax.sort_order, Tax.name)
    )
    return list(rows.all())


@router.post(
    "/properties/{property_id}/taxes", response_model=TaxOut, status_code=status.HTTP_201_CREATED
)
async def create_tax(
    property_id: uuid.UUID, body: TaxCreate, auth: CanManage, request: Request, db: DB
) -> Tax:
    prop = await get_property(db, property_id, auth, Permission.RATES_MANAGE)
    tax = Tax(organisation_id=prop.organisation_id, property_id=prop.id, **body.model_dump())
    db.add(tax)
    await _flush(db, TAX_CONFLICTS)
    await _audit(
        db, auth, request, "tax.created", tax, {"name": tax.name, "rate": str(tax.rate_percent)}
    )
    return tax


@router.patch("/taxes/{tax_id}", response_model=TaxOut)
async def update_tax(
    tax_id: uuid.UUID, body: TaxUpdate, auth: CanManage, request: Request, db: DB
) -> Tax:
    tax = await db.get(Tax, tax_id)
    if tax is None:
        raise not_found("Tax")
    auth.require_for_property(Permission.RATES_MANAGE, tax.property_id)
    changes = body.model_dump(exclude_unset=True)
    _reject_nulls(changes, set())
    diff = audit.apply_changes(tax, changes)
    if diff["after"]:
        await _flush(db, TAX_CONFLICTS)
        await _audit(db, auth, request, "tax.updated", tax, diff)
    return tax


# --- rate plans -------------------------------------------------------------------------


async def _detail(db: DB, plan: RatePlan) -> RatePlanDetail:
    prices = (
        await db.scalars(select(RatePlanPrice).where(RatePlanPrice.rate_plan_id == plan.id))
    ).all()
    seasons = (
        await db.scalars(
            select(SeasonalRate)
            .where(SeasonalRate.rate_plan_id == plan.id)
            .order_by(SeasonalRate.start_date, SeasonalRate.name)
        )
    ).all()
    return RatePlanDetail(
        **RatePlanOut.model_validate(plan).model_dump(),
        prices=[PriceOut.model_validate(p) for p in prices],
        seasons=[SeasonOut.model_validate(s) for s in seasons],
    )


@router.get("/properties/{property_id}/rate-plans", response_model=list[RatePlanOut])
async def list_rate_plans(property_id: uuid.UUID, auth: CanView, db: DB) -> list[RatePlan]:
    await get_property(db, property_id, auth, Permission.RATES_VIEW)
    rows = await db.scalars(
        select(RatePlan)
        .where(RatePlan.property_id == property_id)
        .order_by(RatePlan.status, RatePlan.sort_order, RatePlan.name)
    )
    return list(rows.all())


@router.post(
    "/properties/{property_id}/rate-plans",
    response_model=RatePlanDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_rate_plan(
    property_id: uuid.UUID, body: RatePlanCreate, auth: CanManage, request: Request, db: DB
) -> RatePlanDetail:
    prop = await get_property(db, property_id, auth, Permission.RATES_MANAGE)
    plan = RatePlan(
        organisation_id=prop.organisation_id,
        property_id=prop.id,
        currency=prop.currency,
        **body.model_dump(),
    )
    db.add(plan)
    await _flush(db, PLAN_CONFLICTS)
    await _audit(
        db, auth, request, "rate_plan.created", plan, {"name": plan.name, "code": plan.code}
    )
    return await _detail(db, plan)


@router.get("/rate-plans/{plan_id}", response_model=RatePlanDetail)
async def read_rate_plan(plan_id: uuid.UUID, auth: CanView, db: DB) -> RatePlanDetail:
    return await _detail(db, await _plan(db, auth, plan_id, Permission.RATES_VIEW))


@router.patch("/rate-plans/{plan_id}", response_model=RatePlanDetail)
async def update_rate_plan(
    plan_id: uuid.UUID, body: RatePlanUpdate, auth: CanManage, request: Request, db: DB
) -> RatePlanDetail:
    plan = await _plan(db, auth, plan_id, Permission.RATES_MANAGE)
    changes = body.model_dump(exclude_unset=True)
    _reject_nulls(changes, {"description", "stay_from", "stay_to", "max_stay_nights"})
    merged = {k: changes.get(k, getattr(plan, k)) for k in ("stay_from", "stay_to")}
    if merged["stay_from"] and merged["stay_to"] and merged["stay_to"] < merged["stay_from"]:
        raise HTTPException(status_code=422, detail="The last night must be on or after the first.")
    min_stay = changes.get("min_stay_nights", plan.min_stay_nights)
    max_stay = changes.get("max_stay_nights", plan.max_stay_nights)
    if max_stay is not None and max_stay < min_stay:
        raise HTTPException(status_code=422, detail="Maximum stay must be at least the minimum.")
    diff = audit.apply_changes(plan, changes)
    if diff["after"]:
        await _flush(db, PLAN_CONFLICTS)
        await _audit(db, auth, request, "rate_plan.updated", plan, diff)
    return await _detail(db, plan)


@router.put("/rate-plans/{plan_id}/prices/{room_type_id}", response_model=RatePlanDetail)
async def set_price(
    plan_id: uuid.UUID,
    room_type_id: uuid.UUID,
    body: PriceFields,
    auth: CanManage,
    request: Request,
    db: DB,
) -> RatePlanDetail:
    plan = await _plan(db, auth, plan_id, Permission.RATES_MANAGE)
    rt = await _room_type_of(db, plan.property_id, room_type_id)
    price = await db.scalar(
        select(RatePlanPrice).where(
            RatePlanPrice.rate_plan_id == plan.id, RatePlanPrice.room_type_id == rt.id
        )
    )
    values = body.model_dump()
    if price is None:
        price = RatePlanPrice(
            organisation_id=plan.organisation_id,
            property_id=plan.property_id,
            rate_plan_id=plan.id,
            room_type_id=rt.id,
            **values,
        )
        db.add(price)
        diff: dict[str, Any] = {"after": {k: str(v) for k, v in values.items()}}
    else:
        diff = audit.apply_changes(price, values)
    await db.flush()
    await _audit(db, auth, request, "rate_plan.price_set", plan, {"room_type": rt.code, **diff})
    return await _detail(db, plan)


@router.delete("/rate-plans/{plan_id}/prices/{room_type_id}", response_model=RatePlanDetail)
async def clear_price(
    plan_id: uuid.UUID, room_type_id: uuid.UUID, auth: CanManage, request: Request, db: DB
) -> RatePlanDetail:
    plan = await _plan(db, auth, plan_id, Permission.RATES_MANAGE)
    price = await db.scalar(
        select(RatePlanPrice).where(
            RatePlanPrice.rate_plan_id == plan.id, RatePlanPrice.room_type_id == room_type_id
        )
    )
    if price is not None:
        await db.delete(price)
        await db.flush()
        await _audit(
            db, auth, request, "rate_plan.price_cleared", plan, {"room_type_id": str(room_type_id)}
        )
    return await _detail(db, plan)


# --- seasons ----------------------------------------------------------------------------


@router.post(
    "/rate-plans/{plan_id}/seasons", response_model=SeasonOut, status_code=status.HTTP_201_CREATED
)
async def create_season(
    plan_id: uuid.UUID, body: SeasonCreate, auth: CanManage, request: Request, db: DB
) -> SeasonalRate:
    plan = await _plan(db, auth, plan_id, Permission.RATES_MANAGE)
    await _room_type_of(db, plan.property_id, body.room_type_id)
    season = SeasonalRate(
        organisation_id=plan.organisation_id,
        property_id=plan.property_id,
        rate_plan_id=plan.id,
        **body.model_dump(),
    )
    db.add(season)
    await _flush(db, SEASON_CONFLICTS)
    await _audit(
        db,
        auth,
        request,
        "season.created",
        season,
        {"name": season.name, "from": str(season.start_date), "to": str(season.end_date)},
    )
    return season


async def _season(db: DB, auth: AuthContext, season_id: uuid.UUID) -> SeasonalRate:
    season = await db.get(SeasonalRate, season_id)
    if season is None:
        raise not_found("Season")
    auth.require_for_property(Permission.RATES_MANAGE, season.property_id)
    return season


@router.patch("/seasons/{season_id}", response_model=SeasonOut)
async def update_season(
    season_id: uuid.UUID, body: SeasonUpdate, auth: CanManage, request: Request, db: DB
) -> SeasonalRate:
    season = await _season(db, auth, season_id)
    changes = body.model_dump(exclude_unset=True)
    _reject_nulls(changes, {"weekend_price"})
    start = changes.get("start_date", season.start_date)
    end = changes.get("end_date", season.end_date)
    if end < start:
        raise HTTPException(status_code=422, detail="The last night must be on or after the first.")
    diff = audit.apply_changes(season, changes)
    if diff["after"]:
        await _flush(db, SEASON_CONFLICTS)
        await _audit(db, auth, request, "season.updated", season, diff)
    return season


@router.delete("/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_season(season_id: uuid.UUID, auth: CanManage, request: Request, db: DB) -> None:
    season = await _season(db, auth, season_id)
    await _audit(db, auth, request, "season.deleted", season, {"name": season.name})
    await db.delete(season)
    await db.flush()


# --- quote ------------------------------------------------------------------------------


@router.post("/properties/{property_id}/quote", response_model=QuoteOut)
async def quote(property_id: uuid.UUID, body: QuoteRequest, auth: CanView, db: DB) -> QuoteOut:
    """Price a stay. Reservations use the same function and store its breakdown."""
    prop: Property = await get_property(db, property_id, auth, Permission.RATES_VIEW)
    try:
        priced = await price_stay(
            db,
            prop,
            rate_plan_id=body.rate_plan_id,
            room_type_id=body.room_type_id,
            check_in=body.check_in,
            check_out=body.check_out,
            adults=body.adults,
            children=body.children,
        )
    except pricing.QuoteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    result, plan, rt = priced.quote, priced.plan, priced.room_type
    return QuoteOut(
        currency=result.currency,
        prices_include_tax=result.prices_include_tax,
        rate_plan_id=plan.id,
        rate_plan_name=plan.name,
        room_type_id=rt.id,
        room_type_name=rt.name,
        nights=[NightOut(**n.__dict__) for n in result.nights],
        accommodation_total=result.accommodation_total,
        net_total=result.net_total,
        taxes=[TaxAmountOut(**t.__dict__) for t in result.taxes],
        tax_total=result.tax_total,
        total=result.total,
    )
