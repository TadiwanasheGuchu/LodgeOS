"""Price calculation for a stay. Pure functions: no database access, fully unit-tested.

Rules
- A stay's nights are check_in .. check_out - 1. Each night is priced on its own.
- A night inside a season uses the season's prices; otherwise the plan's normal prices.
- On the property's weekend nights, ``weekend_price`` (when set) replaces ``base_price``.
- ``base_price`` covers the room type's base occupancy. Adults fill the included places
  first; guests beyond them pay the extra-adult or extra-child price.
- All amounts are Decimal and rounded to cents with ROUND_HALF_UP only where stated.
- Taxes are calculated on the net accommodation total, not compounded. When prices include
  tax, net = total / (1 + sum of rates), rounded once; the tax total is the difference, and
  is split across taxes in proportion to their rates, with any rounding cent on the last.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HUNDRED = Decimal(100)
MAX_NIGHTS = 90


class QuoteError(ValueError):
    """The stay cannot be priced; the message is shown to staff."""


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Prices:
    base_price: Decimal
    weekend_price: Decimal | None
    extra_adult_price: Decimal
    extra_child_price: Decimal


@dataclass(frozen=True)
class Season:
    name: str
    start_date: date
    end_date: date  # inclusive
    prices: Prices


@dataclass(frozen=True)
class TaxRate:
    name: str
    rate_percent: Decimal


@dataclass(frozen=True)
class PlanRules:
    currency: str
    prices_include_tax: bool
    min_stay_nights: int = 1
    max_stay_nights: int | None = None
    stay_from: date | None = None
    stay_to: date | None = None


@dataclass(frozen=True)
class Occupancy:
    base: int
    max_total: int
    max_adults: int
    max_children: int


@dataclass(frozen=True)
class NightPrice:
    date: date
    season: str | None
    weekend: bool
    room_price: Decimal
    extra_adults: int
    extra_adult_amount: Decimal
    extra_children: int
    extra_child_amount: Decimal
    amount: Decimal


@dataclass(frozen=True)
class TaxAmount:
    name: str
    rate_percent: Decimal
    amount: Decimal


@dataclass(frozen=True)
class Quote:
    currency: str
    prices_include_tax: bool
    nights: list[NightPrice]
    # Sum of nightly amounts as priced (gross if prices include tax, otherwise net).
    accommodation_total: Decimal
    net_total: Decimal
    taxes: list[TaxAmount] = field(default_factory=list)
    tax_total: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")


def _check_stay(
    rules: PlanRules, occ: Occupancy, check_in: date, check_out: date, adults: int, children: int
) -> int:
    nights = (check_out - check_in).days
    if nights < 1:
        raise QuoteError("Check-out must be after check-in.")
    if nights > MAX_NIGHTS:
        raise QuoteError(f"Stays longer than {MAX_NIGHTS} nights need to be split.")
    if adults < 1:
        raise QuoteError("At least one adult is required.")
    if children < 0:
        raise QuoteError("Children cannot be negative.")
    if adults > occ.max_adults:
        raise QuoteError(f"This room type takes at most {occ.max_adults} adults.")
    if children > occ.max_children:
        raise QuoteError(f"This room type takes at most {occ.max_children} children.")
    if adults + children > occ.max_total:
        raise QuoteError(f"This room type takes at most {occ.max_total} guests.")
    if nights < rules.min_stay_nights:
        raise QuoteError(f"This rate needs a stay of at least {rules.min_stay_nights} nights.")
    if rules.max_stay_nights is not None and nights > rules.max_stay_nights:
        raise QuoteError(f"This rate allows at most {rules.max_stay_nights} nights.")
    last_night = check_out - timedelta(days=1)
    if rules.stay_from is not None and check_in < rules.stay_from:
        raise QuoteError(f"This rate is only for stays from {rules.stay_from.isoformat()}.")
    if rules.stay_to is not None and last_night > rules.stay_to:
        raise QuoteError(f"This rate is only for nights up to {rules.stay_to.isoformat()}.")
    return nights


def _season_for(night: date, seasons: Sequence[Season]) -> Season | None:
    # The database guarantees seasons for one plan and room type do not overlap.
    for s in seasons:
        if s.start_date <= night <= s.end_date:
            return s
    return None


def _split_taxes(net: Decimal, tax_total: Decimal, taxes: Sequence[TaxRate]) -> list[TaxAmount]:
    """Split ``tax_total`` across taxes in proportion to their rates. Every amount but the
    last is rounded on its own; the last takes the remainder, so the parts always add up."""
    if not taxes:
        return []
    parts: list[TaxAmount] = []
    for t in taxes[:-1]:
        parts.append(TaxAmount(t.name, t.rate_percent, cents(net * t.rate_percent / HUNDRED)))
    last = taxes[-1]
    parts.append(TaxAmount(last.name, last.rate_percent, tax_total - sum(p.amount for p in parts)))
    return parts


def quote(
    *,
    rules: PlanRules,
    occupancy: Occupancy,
    normal_prices: Prices | None,
    seasons: Sequence[Season],
    taxes: Sequence[TaxRate],
    weekend_nights: Sequence[int],
    check_in: date,
    check_out: date,
    adults: int,
    children: int = 0,
) -> Quote:
    nights_count = _check_stay(rules, occupancy, check_in, check_out, adults, children)

    extra_adults = max(0, adults - occupancy.base)
    places_left = max(0, occupancy.base - adults)
    extra_children = max(0, children - places_left)

    nights: list[NightPrice] = []
    for i in range(nights_count):
        night = check_in + timedelta(days=i)
        season = _season_for(night, seasons)
        prices = season.prices if season else normal_prices
        if prices is None:
            raise QuoteError(f"No price is set for the night of {night.isoformat()}.")
        weekend = night.isoweekday() in weekend_nights
        room = (
            prices.weekend_price
            if weekend and prices.weekend_price is not None
            else prices.base_price
        )
        adult_amount = prices.extra_adult_price * extra_adults
        child_amount = prices.extra_child_price * extra_children
        nights.append(
            NightPrice(
                date=night,
                season=season.name if season else None,
                weekend=weekend,
                room_price=room,
                extra_adults=extra_adults,
                extra_adult_amount=adult_amount,
                extra_children=extra_children,
                extra_child_amount=child_amount,
                amount=room + adult_amount + child_amount,
            )
        )

    total = cents(sum((n.amount for n in nights), Decimal(0)))
    rate_sum = sum((t.rate_percent for t in taxes), Decimal(0))
    if rules.prices_include_tax:
        net = cents(total / (1 + rate_sum / HUNDRED))
        tax_total = total - net
        gross = total
    else:
        net = total
        tax_total = sum((cents(net * t.rate_percent / HUNDRED) for t in taxes), Decimal("0.00"))
        gross = net + tax_total

    return Quote(
        currency=rules.currency,
        prices_include_tax=rules.prices_include_tax,
        nights=nights,
        accommodation_total=total,
        net_total=net,
        taxes=_split_taxes(net, tax_total, taxes),
        tax_total=tax_total,
        total=gross,
    )
