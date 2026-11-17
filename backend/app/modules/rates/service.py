"""Pricing a stay from the database: shared by the quote endpoint and reservations."""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.properties.models import Property, RecordStatus
from app.modules.rates import pricing
from app.modules.rates.models import RatePlan, RatePlanPrice, SeasonalRate, Tax
from app.modules.rooms.models import RoomType


@dataclass(frozen=True)
class PricedStay:
    quote: pricing.Quote
    plan: RatePlan
    room_type: RoomType


def _prices(row: RatePlanPrice | SeasonalRate) -> pricing.Prices:
    return pricing.Prices(
        row.base_price, row.weekend_price, row.extra_adult_price, row.extra_child_price
    )


async def price_stay(
    db: AsyncSession,
    prop: Property,
    *,
    rate_plan_id: uuid.UUID,
    room_type_id: uuid.UUID,
    check_in: date,
    check_out: date,
    adults: int,
    children: int,
) -> PricedStay:
    """Raises pricing.QuoteError with a message for staff when the stay cannot be priced."""
    plan = await db.get(RatePlan, rate_plan_id)
    if plan is None or plan.property_id != prop.id or plan.status != RecordStatus.ACTIVE:
        raise pricing.QuoteError("Choose an active rate plan of this property.")
    rt = await db.get(RoomType, room_type_id)
    if rt is None or rt.property_id != prop.id:
        raise pricing.QuoteError("Choose a room type from this property.")
    if rt.status != RecordStatus.ACTIVE:
        raise pricing.QuoteError("That room type is archived.")
    normal = await db.scalar(
        select(RatePlanPrice).where(
            RatePlanPrice.rate_plan_id == plan.id, RatePlanPrice.room_type_id == rt.id
        )
    )
    seasons = (
        await db.scalars(
            select(SeasonalRate).where(
                SeasonalRate.rate_plan_id == plan.id,
                SeasonalRate.room_type_id == rt.id,
                SeasonalRate.start_date < check_out,
                SeasonalRate.end_date >= check_in,
            )
        )
    ).all()
    taxes = (
        await db.scalars(
            select(Tax)
            .where(Tax.property_id == prop.id, Tax.status == RecordStatus.ACTIVE)
            .order_by(Tax.sort_order, Tax.name)
        )
    ).all()
    result = pricing.quote(
        rules=pricing.PlanRules(
            currency=plan.currency,
            prices_include_tax=plan.prices_include_tax,
            min_stay_nights=plan.min_stay_nights,
            max_stay_nights=plan.max_stay_nights,
            stay_from=plan.stay_from,
            stay_to=plan.stay_to,
        ),
        occupancy=pricing.Occupancy(
            base=rt.base_occupancy,
            max_total=rt.max_occupancy,
            max_adults=rt.max_adults,
            max_children=rt.max_children,
        ),
        normal_prices=_prices(normal) if normal else None,
        seasons=[pricing.Season(s.name, s.start_date, s.end_date, _prices(s)) for s in seasons],
        taxes=[pricing.TaxRate(t.name, t.rate_percent) for t in taxes],
        weekend_nights=prop.weekend_nights,
        check_in=check_in,
        check_out=check_out,
        adults=adults,
        children=children,
    )
    return PricedStay(result, plan, rt)
