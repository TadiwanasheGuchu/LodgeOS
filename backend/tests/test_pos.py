"""Point of sale (ADR-0015): charge to room or pay now, through invoices and payments."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.modules.organisations.models import Role
from tests.conftest import csrf, login
from tests.test_reservations import _post, _setup
from tests.test_stays import _book


def key() -> str:
    return uuid.uuid4().hex


async def _shop(client, factory):
    org, prop, rt, plan, rooms = await _setup(client, factory)
    vat = (
        await _post(
            client, f"/api/v1/properties/{prop['id']}/taxes", {"name": "VAT", "rate_percent": "15"}
        )
    ).json()
    bar = (
        await _post(client, f"/api/v1/properties/{prop['id']}/pos/outlets", {"name": "Bar"})
    ).json()
    beer = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/pos/items",
            {
                "outlet_id": bar["id"],
                "name": "Windhoek Lager",
                "category": "Beer",
                "price": "45.00",
                "tax_ids": [vat["id"]],
            },
        )
    ).json()
    steak = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/pos/items",
            {
                "outlet_id": bar["id"],
                "name": "Oryx steak",
                "price": "185.00",
                "tax_ids": [vat["id"]],
            },
        )
    ).json()
    return org, prop, rt, plan, rooms, bar, beer, steak


async def _in_house(client, prop, rt, plan, room):
    res = await _book(client, prop, rt, plan, 0, 2, room_id=room["id"])
    r = await _post(client, f"/api/v1/reservations/{res['id']}/check-in", {})
    assert r.status_code == 200, r.text
    return res


async def _sell(client, prop, bar, lines, **extra):
    return await _post(
        client,
        f"/api/v1/properties/{prop['id']}/pos/sales",
        {"outlet_id": bar["id"], "lines": lines, "idempotency_key": key(), **extra},
    )


async def test_charge_to_room_builds_one_folio(client, factory) -> None:
    _, prop, rt, plan, rooms, bar, beer, steak = await _shop(client, factory)
    res = await _in_house(client, prop, rt, plan, rooms[0])
    guests = (await client.get(f"/api/v1/properties/{prop['id']}/pos/in-house")).json()
    assert [(g["reference"], g["rooms"]) for g in guests] == [(res["reference"], ["1"])]

    r = await _sell(
        client,
        prop,
        bar,
        [{"service_id": beer["id"], "quantity": "2"}],
        settlement="room",
        reservation_id=res["id"],
    )
    assert r.status_code == 201, r.text
    sale = r.json()
    assert (sale["total"], sale["room_label"], sale["invoice_number"]) == ("90.00", "1", None)
    await _sell(
        client,
        prop,
        bar,
        [{"service_id": steak["id"]}],
        settlement="room",
        reservation_id=res["id"],
    )

    folio = (await client.get(f"/api/v1/invoices/{sale['invoice_id']}")).json()
    assert folio["status"] == "draft" and folio["reservation_id"] == res["id"]
    # The stay itself plus both bar sales, on one bill.
    assert [i["description"] for i in folio["items"]][1:] == [
        "Bar: Windhoek Lager",
        "Bar: Oryx steak",
    ]
    assert [i["total_amount"] for i in folio["items"]][1:] == ["90.00", "185.00"]
    assert folio["items"][0]["kind"] == "accommodation"


async def test_only_checked_in_guests_charge_to_room(client, factory) -> None:
    _, prop, rt, plan, rooms, bar, beer, _ = await _shop(client, factory)
    res = await _book(client, prop, rt, plan, 3, 5, room_id=rooms[0]["id"])
    r = await _sell(
        client, prop, bar, [{"service_id": beer["id"]}], settlement="room", reservation_id=res["id"]
    )
    assert (r.status_code, r.json()["detail"]) == (
        409,
        "Only guests who are checked in can charge to their room.",
    )


async def test_pay_now_issues_invoice_and_records_payment(client, factory) -> None:
    _, prop, _, _, _, bar, beer, steak = await _shop(client, factory)
    body = {
        "outlet_id": bar["id"],
        "lines": [{"service_id": beer["id"]}, {"service_id": steak["id"]}],
        "settlement": "paid",
        "method": "cash",
        "idempotency_key": key(),
    }
    url = f"/api/v1/properties/{prop['id']}/pos/sales"
    first = await _post(client, url, body)
    again = await _post(client, url, body)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    sale = first.json()
    assert sale["total"] == "230.00" and sale["invoice_number"].startswith("INV-")
    money = (await client.get(f"/api/v1/invoices/{sale['invoice_id']}/payments")).json()
    assert (money["paid"], money["balance"]) == ("230.00", "0.00")
    inv = (await client.get(f"/api/v1/invoices/{sale['invoice_id']}")).json()
    assert inv["bill_to_name"] == "Walk-in guest"
    assert inv["tax_total"] == "30.00"  # 15% inside 45.00 + 185.00, each line rounded
    cash = (await client.get(f"/api/v1/properties/{prop['id']}/cash-up")).json()
    assert [(t["method"], t["received"]) for t in cash["totals"]] == [("cash", "230.00")]
    sales = (await client.get(f"/api/v1/properties/{prop['id']}/pos/sales")).json()
    assert len(sales) == 1 and sales[0]["items"][0]["name"] == "Windhoek Lager"
    r = await _sell(client, prop, bar, [{"service_id": beer["id"]}], settlement="paid")
    assert r.json()["detail"] == "Choose how the guest paid."


async def test_items_must_belong_to_the_outlet_and_be_active(client, factory) -> None:
    _, prop, _, _, _, bar, beer, _ = await _shop(client, factory)
    shop = (
        await _post(client, f"/api/v1/properties/{prop['id']}/pos/outlets", {"name": "Curio shop"})
    ).json()
    r = await _sell(
        client, prop, shop, [{"service_id": beer["id"]}], settlement="paid", method="card"
    )
    assert r.json()["detail"] == "Choose items sold at this outlet."
    await client.patch(
        f"/api/v1/pos/items/{beer['id']}", json={"status": "archived"}, headers=await csrf(client)
    )
    r = await _sell(
        client, prop, bar, [{"service_id": beer["id"]}], settlement="paid", method="card"
    )
    assert r.status_code == 422


async def test_sales_are_final_in_the_database(client, factory, app_engine) -> None:
    org, prop, _, _, _, bar, beer, _ = await _shop(client, factory)
    sale = (
        await _sell(
            client, prop, bar, [{"service_id": beer["id"]}], settlement="paid", method="cash"
        )
    ).json()
    for sql in (
        "UPDATE pos_orders SET total = 1 WHERE id = :id",
        "DELETE FROM pos_orders WHERE id = :id",
    ):
        async with app_engine.connect() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_org_id', :o, true)"), {"o": str(org.id)}
            )
            with pytest.raises(DBAPIError):
                await conn.execute(text(sql), {"id": uuid.UUID(sale["id"])})
            await conn.rollback()


async def test_permissions(client, factory) -> None:
    org, prop, _, _, _, bar, beer, _ = await _shop(client, factory)
    front = await factory.user()
    await factory.member(org, front, Role.RECEPTIONIST)
    await login(client, front.email)
    r = await _sell(
        client, prop, bar, [{"service_id": beer["id"]}], settlement="paid", method="card"
    )
    assert r.status_code == 201
    r = await _post(client, f"/api/v1/properties/{prop['id']}/pos/outlets", {"name": "Pool bar"})
    assert r.status_code == 403  # selling, not managing the catalogue
    keeper = await factory.user()
    await factory.member(org, keeper, Role.HOUSEKEEPING)
    await login(client, keeper.email)
    assert (await client.get(f"/api/v1/properties/{prop['id']}/pos/items")).status_code == 403
    other = await factory.organisation("Elsewhere")
    stranger = await factory.user()
    await factory.member(other, stranger, Role.OWNER)
    await login(client, stranger.email)
    assert (await client.get(f"/api/v1/properties/{prop['id']}/pos/items")).status_code == 404
