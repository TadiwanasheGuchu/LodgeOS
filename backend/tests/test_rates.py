"""Rate plans, prices, seasons, taxes and quotes through the API."""

from decimal import Decimal as D

from app.modules.organisations.models import Role
from tests.conftest import Factory, csrf, login


async def _post(client, url, body):
    return await client.post(url, json=body, headers=await csrf(client))


async def _put(client, url, body):
    return await client.put(url, json=body, headers=await csrf(client))


async def _patch(client, url, body):
    return await client.patch(url, json=body, headers=await csrf(client))


async def _setup(client, factory: Factory):
    org = await factory.organisation("Damaraland Group")
    owner = await factory.user()
    await factory.member(org, owner, Role.OWNER)
    await login(client, owner.email)
    prop = (
        await _post(
            client, "/api/v1/properties", {"name": "Twyfelfontein Lodge", "property_type": "lodge"}
        )
    ).json()
    rt = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/room-types",
            {
                "name": "Double",
                "code": "DBL",
                "base_occupancy": 2,
                "max_occupancy": 3,
                "max_adults": 3,
                "max_children": 1,
            },
        )
    ).json()
    plan = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/rate-plans",
            {"name": "Bed and breakfast", "code": "BB", "meal_plan": "bed_and_breakfast"},
        )
    ).json()
    return org, prop, rt, plan


async def test_full_quote_through_the_api(client, factory) -> None:
    _, prop, rt, plan = await _setup(client, factory)
    assert plan["currency"] == "NAD"
    assert plan["prices_include_tax"] is True

    r = await _put(
        client,
        f"/api/v1/rate-plans/{plan['id']}/prices/{rt['id']}",
        {"base_price": "1000.00", "weekend_price": "1200.00", "extra_adult_price": "350.00"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["prices"][0]["base_price"] == "1000.00"  # money is a string, never a float

    await _post(
        client, f"/api/v1/properties/{prop['id']}/taxes", {"name": "VAT", "rate_percent": "15"}
    )
    await _post(
        client,
        f"/api/v1/properties/{prop['id']}/taxes",
        {"name": "Tourism levy", "rate_percent": "1", "sort_order": 1},
    )
    r = await _post(
        client,
        f"/api/v1/rate-plans/{plan['id']}/seasons",
        {
            "room_type_id": rt["id"],
            "name": "Festive",
            "start_date": "2026-12-20",
            "end_date": "2027-01-05",
            "base_price": "1500.00",
        },
    )
    assert r.status_code == 201, r.text

    # Fri 18, Sat 19 (weekend, normal), Sun 20 and Mon 21 (festive), 3 adults.
    r = await _post(
        client,
        f"/api/v1/properties/{prop['id']}/quote",
        {
            "rate_plan_id": plan["id"],
            "room_type_id": rt["id"],
            "check_in": "2026-12-18",
            "check_out": "2026-12-22",
            "adults": 3,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [n["amount"] for n in body["nights"]] == ["1550.00", "1550.00", "1500.00", "1500.00"]
    # Festive season has no extra-adult price set (0.00), so its nights are 1500.
    assert [n["season"] for n in body["nights"]] == [None, None, "Festive", "Festive"]
    total = D(body["total"])
    assert total == D("6100.00")
    assert D(body["net_total"]) + sum(D(t["amount"]) for t in body["taxes"]) == total
    assert [t["name"] for t in body["taxes"]] == ["VAT", "Tourism levy"]


async def test_overlapping_seasons_are_refused(client, factory) -> None:
    _, _, rt, plan = await _setup(client, factory)
    url = f"/api/v1/rate-plans/{plan['id']}/seasons"
    base = {"room_type_id": rt["id"], "base_price": "900.00"}
    a = await _post(
        client, url, base | {"name": "Winter", "start_date": "2027-06-01", "end_date": "2027-08-31"}
    )
    assert a.status_code == 201
    r = await _post(
        client,
        url,
        base | {"name": "School holidays", "start_date": "2027-08-31", "end_date": "2027-09-10"},
    )
    assert r.status_code == 409  # 31 August is in both
    assert "overlap" in r.json()["detail"]
    assert (
        await _post(
            client,
            url,
            base | {"name": "Spring", "start_date": "2027-09-01", "end_date": "2027-09-10"},
        )
    ).status_code == 201
    # Moving a season into another is refused too.
    r = await _patch(client, f"/api/v1/seasons/{a.json()['id']}", {"end_date": "2027-09-02"})
    assert r.status_code == 409
    assert (
        await _post(
            client,
            url,
            base | {"name": "Backwards", "start_date": "2027-10-02", "end_date": "2027-10-01"},
        )
    ).status_code == 422


async def test_quote_errors_are_explained(client, factory) -> None:
    _, prop, rt, plan = await _setup(client, factory)
    url = f"/api/v1/properties/{prop['id']}/quote"
    stay = {
        "rate_plan_id": plan["id"],
        "room_type_id": rt["id"],
        "check_in": "2026-12-01",
        "check_out": "2026-12-03",
        "adults": 2,
    }
    r = await _post(client, url, stay)
    assert r.status_code == 422
    assert r.json()["detail"] == "No price is set for the night of 2026-12-01."
    await _put(
        client, f"/api/v1/rate-plans/{plan['id']}/prices/{rt['id']}", {"base_price": "800.00"}
    )
    assert (await _post(client, url, stay | {"adults": 4})).json()[
        "detail"
    ] == "This room type takes at most 3 adults."
    await _patch(client, f"/api/v1/rate-plans/{plan['id']}", {"min_stay_nights": 3})
    assert "at least 3 nights" in (await _post(client, url, stay)).json()["detail"]


async def test_money_validation(client, factory) -> None:
    _, prop, rt, plan = await _setup(client, factory)
    url = f"/api/v1/rate-plans/{plan['id']}/prices/{rt['id']}"
    for bad in ({"base_price": "-1.00"}, {"base_price": "10.001"}, {"base_price": "abc"}):
        assert (await _put(client, url, bad)).status_code == 422, bad
    for bad in ({"name": "VAT", "rate_percent": "0"}, {"name": "VAT", "rate_percent": "100"}):
        assert (
            await _post(client, f"/api/v1/properties/{prop['id']}/taxes", bad)
        ).status_code == 422


async def test_weekend_nights_are_configurable(client, factory) -> None:
    _, prop, rt, plan = await _setup(client, factory)
    assert prop["weekend_nights"] == [5, 6]
    r = await _patch(client, f"/api/v1/properties/{prop['id']}", {"weekend_nights": [6, 6, 7]})
    assert r.json()["weekend_nights"] == [6, 7]
    assert (
        await _patch(client, f"/api/v1/properties/{prop['id']}", {"weekend_nights": [8]})
    ).status_code == 422
    await _put(
        client,
        f"/api/v1/rate-plans/{plan['id']}/prices/{rt['id']}",
        {"base_price": "100.00", "weekend_price": "200.00"},
    )
    # Fri 4 Dec 2026 is no longer a weekend night; Sat and Sun are.
    r = await _post(
        client,
        f"/api/v1/properties/{prop['id']}/quote",
        {
            "rate_plan_id": plan["id"],
            "room_type_id": rt["id"],
            "check_in": "2026-12-04",
            "check_out": "2026-12-07",
            "adults": 1,
        },
    )
    assert [n["room_price"] for n in r.json()["nights"]] == ["100.00", "200.00", "200.00"]


async def test_rate_permissions(client, factory) -> None:
    org, prop, rt, plan = await _setup(client, factory)
    await client.post("/api/v1/auth/logout", headers=await csrf(client))

    desk = await factory.user()
    await factory.member(org, desk, Role.RECEPTIONIST)
    await login(client, desk.email)
    assert (await client.get(f"/api/v1/rate-plans/{plan['id']}")).status_code == 200
    assert (
        await _put(
            client, f"/api/v1/rate-plans/{plan['id']}/prices/{rt['id']}", {"base_price": "1.00"}
        )
    ).status_code == 403
    assert (
        await _post(
            client, f"/api/v1/properties/{prop['id']}/taxes", {"name": "X", "rate_percent": "1"}
        )
    ).status_code == 403
    await client.post("/api/v1/auth/logout", headers=await csrf(client))

    hk = await factory.user()
    await factory.member(org, hk, Role.HOUSEKEEPING)
    await login(client, hk.email)
    assert (await client.get(f"/api/v1/properties/{prop['id']}/rate-plans")).status_code == 403


async def test_other_tenant_cannot_see_rates(client, factory) -> None:
    _, prop, _, plan = await _setup(client, factory)
    await client.post("/api/v1/auth/logout", headers=await csrf(client))
    other = await factory.organisation("Other")
    u = await factory.user()
    await factory.member(other, u, Role.OWNER)
    await login(client, u.email)
    assert (await client.get(f"/api/v1/rate-plans/{plan['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/properties/{prop['id']}/taxes")).status_code == 404
