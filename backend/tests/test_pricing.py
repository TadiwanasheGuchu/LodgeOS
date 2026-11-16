"""Pricing engine. Expected values are worked out by hand in the comments."""

import random
from datetime import date
from decimal import Decimal as D

import pytest

from app.modules.rates.pricing import (
    Occupancy,
    PlanRules,
    Prices,
    QuoteError,
    Season,
    TaxRate,
    quote,
)

RULES_INCL = PlanRules(currency="NAD", prices_include_tax=True)
RULES_EXCL = PlanRules(currency="NAD", prices_include_tax=False)
DOUBLE = Occupancy(base=2, max_total=4, max_adults=3, max_children=2)
NORMAL = Prices(D("1000.00"), None, D("300.00"), D("150.00"))
VAT_AND_LEVY = [TaxRate("VAT", D("15")), TaxRate("Tourism levy", D("1"))]
FRI_SAT = [5, 6]


def q(**kw):
    args = dict(
        rules=RULES_INCL,
        occupancy=DOUBLE,
        normal_prices=NORMAL,
        seasons=[],
        taxes=VAT_AND_LEVY,
        weekend_nights=FRI_SAT,
        check_in=date(2026, 11, 16),  # Monday
        check_out=date(2026, 11, 18),
        adults=2,
        children=0,
    )
    args.update(kw)
    return quote(**args)


def test_tax_inclusive_split() -> None:
    r = q()
    # 2 nights x 1000.00 = 2000.00 including 16% tax.
    # net = 2000 / 1.16 = 1724.137... -> 1724.14; tax = 275.86
    # VAT = 1724.14 x 15% = 258.621 -> 258.62; levy takes the rest = 17.24
    assert r.accommodation_total == D("2000.00")
    assert r.net_total == D("1724.14")
    assert [(t.name, t.amount) for t in r.taxes] == [
        ("VAT", D("258.62")),
        ("Tourism levy", D("17.24")),
    ]
    assert r.tax_total == D("275.86")
    assert r.total == D("2000.00")
    assert all(not n.weekend and n.season is None for n in r.nights)


def test_tax_exclusive() -> None:
    r = q(
        rules=RULES_EXCL,
        normal_prices=Prices(D("999.99"), None, D(0), D(0)),
        taxes=[TaxRate("VAT", D("15"))],
        check_out=date(2026, 11, 17),
    )
    # 999.99 x 15% = 149.9985 -> 150.00
    assert (r.net_total, r.tax_total, r.total) == (D("999.99"), D("150.00"), D("1149.99"))


def test_no_taxes() -> None:
    r = q(taxes=[])
    assert (r.net_total, r.tax_total, r.total, r.taxes) == (
        D("2000.00"),
        D("0.00"),
        D("2000.00"),
        [],
    )


def test_weekend_nights_use_weekend_price() -> None:
    prices = Prices(D("1000.00"), D("1200.00"), D(0), D(0))
    # Fri 20, Sat 21, Sun 22 November 2026: Friday and Saturday are weekend nights.
    r = q(normal_prices=prices, check_in=date(2026, 11, 20), check_out=date(2026, 11, 23))
    assert [n.room_price for n in r.nights] == [D("1200.00"), D("1200.00"), D("1000.00")]
    assert [n.weekend for n in r.nights] == [True, True, False]
    assert r.accommodation_total == D("3400.00")
    # A property can choose different weekend nights.
    r = q(
        normal_prices=prices,
        check_in=date(2026, 11, 20),
        check_out=date(2026, 11, 23),
        weekend_nights=[7],
    )
    assert [n.room_price for n in r.nights] == [D("1000.00"), D("1000.00"), D("1200.00")]


def test_season_overrides_normal_prices_night_by_night() -> None:
    festive = Season(
        "Festive", date(2026, 12, 20), date(2027, 1, 5), Prices(D("1500.00"), None, D(0), D(0))
    )
    r = q(seasons=[festive], check_in=date(2026, 12, 18), check_out=date(2026, 12, 22))
    # 18 and 19 Dec normal (no weekend price set), 20 and 21 Dec festive.
    assert [n.room_price for n in r.nights] == [
        D("1000.00"),
        D("1000.00"),
        D("1500.00"),
        D("1500.00"),
    ]
    assert [n.season for n in r.nights] == [None, None, "Festive", "Festive"]
    assert r.accommodation_total == D("5000.00")


def test_season_last_day_is_inclusive_and_season_weekend_price() -> None:
    s = Season(
        "Peak", date(2026, 11, 20), date(2026, 11, 21), Prices(D("800.00"), D("900.00"), D(0), D(0))
    )
    r = q(seasons=[s], check_in=date(2026, 11, 20), check_out=date(2026, 11, 23))
    assert [n.room_price for n in r.nights] == [D("900.00"), D("900.00"), D("1000.00")]


def test_extra_guests() -> None:
    # Base 2: 3 adults + 1 child -> 1 extra adult and 1 extra child.
    r = q(adults=3, children=1, check_out=date(2026, 11, 17))
    n = r.nights[0]
    assert (n.extra_adults, n.extra_children) == (1, 1)
    assert n.amount == D("1450.00")  # 1000 + 300 + 150
    # 1 adult + 2 children: one child fills the second included place.
    n = q(adults=1, children=2, check_out=date(2026, 11, 17)).nights[0]
    assert (n.extra_adults, n.extra_children, n.amount) == (0, 1, D("1150.00"))
    # 1 adult + 1 child fits the base price.
    assert q(adults=1, children=1, check_out=date(2026, 11, 17)).nights[0].amount == D("1000.00")


@pytest.mark.parametrize(
    ("kw", "message"),
    [
        ({"check_out": date(2026, 11, 16)}, "after check-in"),
        ({"check_out": date(2027, 3, 1)}, "longer than 90"),
        ({"adults": 0}, "one adult"),
        ({"adults": 4}, "at most 3 adults"),
        ({"children": 3}, "at most 2 children"),
        ({"adults": 3, "children": 2}, "at most 4 guests"),
        ({"rules": PlanRules("NAD", True, min_stay_nights=3)}, "at least 3 nights"),
        ({"rules": PlanRules("NAD", True, max_stay_nights=1)}, "at most 1 nights"),
        ({"rules": PlanRules("NAD", True, stay_from=date(2026, 11, 17))}, "from 2026-11-17"),
        ({"rules": PlanRules("NAD", True, stay_to=date(2026, 11, 16))}, "up to 2026-11-16"),
        ({"normal_prices": None}, "No price is set for the night of 2026-11-16"),
    ],
)
def test_stays_that_cannot_be_priced(kw, message) -> None:
    with pytest.raises(QuoteError, match=message):
        q(**kw)


def test_stay_window_allows_last_night_on_stay_to() -> None:
    # Checking out on 18th means the last night is the 17th, inside the window.
    r = q(rules=PlanRules("NAD", True, stay_to=date(2026, 11, 17)))
    assert len(r.nights) == 2


def test_parts_always_add_up_exactly() -> None:
    """Across many random prices and tax rates, net + taxes == total to the cent and no
    tax amount is negative."""
    rng = random.Random(20261116)
    for _ in range(2000):
        price = D(rng.randint(1, 5_000_000)) / 100
        taxes = [TaxRate(f"T{i}", D(rng.randint(1, 2500)) / 100) for i in range(rng.randint(0, 3))]
        nights = rng.randint(1, 14)
        for include in (True, False):
            r = q(
                rules=PlanRules("NAD", include),
                normal_prices=Prices(price, None, D(0), D(0)),
                taxes=taxes,
                check_out=date(2026, 11, 16 + nights),
            )
            assert r.net_total + sum(t.amount for t in r.taxes) == r.total
            assert r.tax_total == sum((t.amount for t in r.taxes), D(0))
            assert all(t.amount >= 0 for t in r.taxes)
            assert r.total.as_tuple().exponent == -2
