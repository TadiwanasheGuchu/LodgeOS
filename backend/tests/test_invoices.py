"""Invoices and credit notes (ADR-0009): exact copies of bookings, gapless numbers, immutable
once issued, corrected only by credit notes."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.modules.organisations.models import Role
from tests.conftest import csrf, login
from tests.test_reservations import _booking, _post, _setup


async def _tax(client, prop, name, rate):
    r = await _post(
        client, f"/api/v1/properties/{prop['id']}/taxes", {"name": name, "rate_percent": rate}
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _booked(client, prop, rt, plan, check_in="2027-01-10", check_out="2027-01-13"):
    r = await _post(
        client,
        f"/api/v1/properties/{prop['id']}/reservations",
        _booking(rt, plan, check_in, check_out),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _invoice_for(client, prop, res, **extra):
    r = await _post(
        client,
        f"/api/v1/properties/{prop['id']}/invoices",
        {"reservation_id": res["id"], **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _issue(client, inv):
    r = await _post(client, f"/api/v1/invoices/{inv['id']}/issue", {})
    assert r.status_code == 200, r.text
    return r.json()


def _sums_hold(doc, items_key="items", amount="amount"):
    for i in doc[items_key]:
        net, tax, total = (Decimal(i[f"{k}_{amount}"]) for k in ("net", "tax", "total"))
        assert net + tax == total
        assert sum(Decimal(t["amount"]) for t in i["taxes"]) == tax
    assert Decimal(doc["net_total"]) + Decimal(doc["tax_total"]) == Decimal(doc["total"])
    assert sum(Decimal(i[f"total_{amount}"]) for i in doc[items_key]) == Decimal(doc["total"])


async def test_invoice_copies_the_booking_and_numbers_are_gapless(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    await _tax(client, prop, "VAT", "15")
    await _tax(client, prop, "Tourism levy", "1")
    res = await _booked(client, prop, rt, plan)

    inv = await _invoice_for(client, prop, res)
    assert (inv["status"], inv["number"], inv["bill_to_name"]) == (
        "draft",
        None,
        "Ndeshi Nghifindaka",
    )
    assert inv["total"] == res["total_amount"] and inv["tax_total"] == res["tax_amount"]
    [line] = inv["items"]
    assert line["description"] == "Tent · Standard · 10 Jan to 13 Jan 2027 (3 nights)"
    assert [t["name"] for t in line["taxes"]] == ["Tourism levy", "VAT"]
    _sums_hold(inv)

    issued = await _issue(client, inv)
    assert issued["number"] == "INV-000001" and issued["issue_date"]
    # A second booking gets the next number; a discarded draft takes none.
    other = await _invoice_for(
        client, prop, await _booked(client, prop, rt, plan, "2027-02-01", "2027-02-02")
    )
    await _post(client, f"/api/v1/invoices/{other['id']}/discard", {})
    third = await _invoice_for(
        client, prop, await _booked(client, prop, rt, plan, "2027-03-01", "2027-03-02")
    )
    assert (await _issue(client, third))["number"] == "INV-000002"


async def test_a_booked_room_is_invoiced_once(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    res = await _booked(client, prop, rt, plan)
    inv = await _invoice_for(client, prop, res)
    r = await _post(
        client, f"/api/v1/properties/{prop['id']}/invoices", {"reservation_id": res["id"]}
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "Every room of this booking is already on an invoice."
    # Discarding the draft frees the room for a new invoice.
    await _post(client, f"/api/v1/invoices/{inv['id']}/discard", {})
    again = await _invoice_for(client, prop, res)
    issued = await _issue(client, again)
    # Fully crediting the line frees it again.
    r = await _post(
        client,
        f"/api/v1/invoices/{issued['id']}/credit-notes",
        {
            "reason": "Billed to the company instead",
            "lines": [{"invoice_item_id": issued["items"][0]["id"]}],
        },
    )
    assert r.status_code == 201, r.text
    company = await _invoice_for(client, prop, res, bill_to_name="Namib Mining (Pty) Ltd")
    assert company["total"] == res["total_amount"]


async def test_extras_use_the_tax_rounding_rule(client, factory) -> None:
    _, prop, _, _, _ = await _setup(client, factory)
    vat = await _tax(client, prop, "VAT", "15")
    r = await _post(
        client, f"/api/v1/properties/{prop['id']}/invoices", {"bill_to_name": "Walk-in diner"}
    )
    inv = r.json()
    assert inv["currency"] == "NAD"
    r = await _post(
        client,
        f"/api/v1/invoices/{inv['id']}/items",
        {"description": "Dinner", "quantity": "3", "unit_amount": "185.50", "tax_ids": [vat["id"]]},
    )
    assert r.status_code == 201, r.text
    [line] = r.json()["items"]
    # 556.50 incl. 15%: net estimate 483.913..., VAT 72.59, net absorbs the cent: 483.91.
    assert (line["total_amount"], line["tax_amount"], line["net_amount"]) == (
        "556.50",
        "72.59",
        "483.91",
    )
    r = await _post(
        client,
        f"/api/v1/invoices/{inv['id']}/items",
        {
            "description": "Laundry",
            "quantity": "1",
            "unit_amount": "100.00",
            "prices_include_tax": False,
            "tax_ids": [vat["id"]],
        },
    )
    doc = r.json()
    assert doc["items"][1]["total_amount"] == "115.00"
    assert doc["total"] == "671.50"
    _sums_hold(doc)
    assert doc["tax_summary"] == [{"name": "VAT", "rate_percent": "15.0000", "amount": "87.59"}]

    # Draft lines can be removed; nothing can be removed or added once issued.
    r = await client.delete(
        f"/api/v1/invoices/{inv['id']}/items/{doc['items'][1]['id']}", headers=await csrf(client)
    )
    assert r.json()["total"] == "556.50"
    await _issue(client, inv)
    r = await _post(
        client,
        f"/api/v1/invoices/{inv['id']}/items",
        {"description": "Wine", "quantity": "1", "unit_amount": "90"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "Issued invoices cannot be changed. Use a credit note."


async def test_credit_notes_split_taxes_and_never_over_credit(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    await _tax(client, prop, "VAT", "15")
    await _tax(client, prop, "Tourism levy", "1")
    inv = await _issue(
        client, await _invoice_for(client, prop, await _booked(client, prop, rt, plan))
    )
    [line] = inv["items"]
    url = f"/api/v1/invoices/{inv['id']}/credit-notes"

    r = await _post(
        client,
        url,
        {"reason": "Late arrival", "lines": [{"invoice_item_id": line["id"], "amount": "1000.00"}]},
    )
    assert r.status_code == 201, r.text
    note = r.json()
    assert note["number"] == "CN-000001" and note["invoice_number"] == "INV-000001"
    _sums_hold(note)
    # Too much is refused with the remaining amount.
    r = await _post(
        client,
        url,
        {"reason": "Again", "lines": [{"invoice_item_id": line["id"], "amount": "2000.01"}]},
    )
    assert r.status_code == 422
    assert "2000.00" in r.json()["detail"]
    # The remainder is credited exactly: every component of the line nets to zero.
    r = await _post(
        client, url, {"reason": "Cancelled", "lines": [{"invoice_item_id": line["id"]}]}
    )
    assert r.status_code == 201
    doc = (await client.get(f"/api/v1/invoices/{inv['id']}")).json()
    assert doc["credited"] == doc["total"] == "3000.00"
    assert doc["items"][0]["credited_amount"] == "3000.00"
    notes = doc["credit_notes"]
    for key in ("net_total", "tax_total"):
        assert sum(Decimal(n[key]) for n in notes) == Decimal(doc[key])
    for i, tax in enumerate(line["taxes"]):
        assert sum(Decimal(n["items"][0]["taxes"][i]["amount"]) for n in notes) == Decimal(
            tax["amount"]
        )
    r = await _post(
        client, url, {"reason": "Once more", "lines": [{"invoice_item_id": line["id"]}]}
    )
    assert r.status_code == 409
    # Drafts cannot be credited.
    draft = await _invoice_for(
        client, prop, await _booked(client, prop, rt, plan, "2027-05-01", "2027-05-02")
    )
    r = await _post(
        client,
        f"/api/v1/invoices/{draft['id']}/credit-notes",
        {"reason": "Not issued yet", "lines": [{"invoice_item_id": draft["items"][0]["id"]}]},
    )
    assert r.status_code == 409


async def test_database_refuses_changes_to_issued_invoices(client, factory, app_engine) -> None:
    org, prop, rt, plan, _ = await _setup(client, factory)
    inv = await _issue(
        client, await _invoice_for(client, prop, await _booked(client, prop, rt, plan))
    )
    statements = [
        "UPDATE invoices SET total = 1, net_total = 1, tax_total = 0 WHERE id = :id",
        "UPDATE invoice_items SET description = 'x' WHERE invoice_id = :id",
        "DELETE FROM invoice_items WHERE invoice_id = :id",
        "DELETE FROM invoices WHERE id = :id",
    ]
    for sql in statements:
        async with app_engine.connect() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_org_id', :o, true)"), {"o": str(org.id)}
            )
            with pytest.raises(DBAPIError):
                await conn.execute(text(sql), {"id": uuid.UUID(inv["id"])})
            await conn.rollback()


async def test_permissions_and_isolation(client, factory) -> None:
    org, prop, rt, plan, _ = await _setup(client, factory)
    inv = await _issue(
        client, await _invoice_for(client, prop, await _booked(client, prop, rt, plan))
    )
    line = {
        "reason": "Goodwill",
        "lines": [{"invoice_item_id": inv["items"][0]["id"], "amount": "10"}],
    }

    front = await factory.user()
    await factory.member(org, front, Role.RECEPTIONIST)
    await login(client, front.email)
    assert (await client.get(f"/api/v1/invoices/{inv['id']}")).status_code == 200
    r = await _post(client, f"/api/v1/invoices/{inv['id']}/credit-notes", line)
    assert r.status_code == 403  # front desk invoices but cannot credit

    keeper = await factory.user()
    await factory.member(org, keeper, Role.HOUSEKEEPING)
    await login(client, keeper.email)
    assert (await client.get(f"/api/v1/invoices/{inv['id']}")).status_code == 403
    assert (await client.get(f"/api/v1/properties/{prop['id']}/invoices")).status_code == 403

    books = await factory.user()
    await factory.member(org, books, Role.ACCOUNTANT)
    await login(client, books.email)
    r = await _post(client, f"/api/v1/invoices/{inv['id']}/credit-notes", line)
    assert r.status_code == 201

    other = await factory.organisation("Elsewhere")
    stranger = await factory.user()
    await factory.member(other, stranger, Role.OWNER)
    await login(client, stranger.email)
    assert (await client.get(f"/api/v1/invoices/{inv['id']}")).status_code == 404
    # Another organisation numbers from 1 on its own.
    _, p2, rt2, plan2, _ = await _setup(client, factory)
    own = await _issue(
        client, await _invoice_for(client, p2, await _booked(client, p2, rt2, plan2))
    )
    assert own["number"] == "INV-000001"


async def test_concurrent_issues_get_distinct_consecutive_numbers(client, factory) -> None:
    import asyncio

    _, prop, rt, plan, _ = await _setup(client, factory, rooms=6)
    drafts = [
        await _invoice_for(
            client,
            prop,
            await _booked(client, prop, rt, plan, f"2027-06-{d:02d}", f"2027-06-{d + 1:02d}"),
        )
        for d in range(1, 6)
    ]
    headers = await csrf(client)
    results = await asyncio.gather(
        *(client.post(f"/api/v1/invoices/{d['id']}/issue", headers=headers) for d in drafts)
    )
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert sorted(r.json()["number"] for r in results) == [f"INV-00000{i}" for i in range(1, 6)]
