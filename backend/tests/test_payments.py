"""Payments, allocations, refunds and cash-up (ADR-0010)."""

import asyncio
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import set_tenant_context
from app.modules.invoicing.models import Invoice
from app.modules.organisations.models import Role
from app.modules.payments import service
from app.modules.payments.models import Payment
from tests.conftest import csrf, login
from tests.test_invoices import _booked, _invoice_for, _issue
from tests.test_reservations import _post, _setup


def key() -> str:
    return uuid.uuid4().hex


async def _pay(client, prop, amount, **extra):
    body = {"method": "card", "amount": amount, "idempotency_key": key(), **extra}
    r = await _post(client, f"/api/v1/properties/{prop['id']}/payments", body)
    assert r.status_code in (200, 201), r.text
    return r.json()


async def _money(client, inv):
    r = await client.get(f"/api/v1/invoices/{inv['id']}/payments")
    assert r.status_code == 200, r.text
    return r.json()


async def _issued(client, factory):
    org, prop, rt, plan, _ = await _setup(client, factory)
    inv = await _issue(
        client, await _invoice_for(client, prop, await _booked(client, prop, rt, plan))
    )
    return org, prop, rt, plan, inv  # total 3000.00 (3 nights at 1000)


async def test_deposit_then_settlement_and_balances(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    res = await _booked(client, prop, rt, plan)
    deposit = await _pay(client, prop, "1000.00", method="bank_transfer", reservation_id=res["id"])
    assert deposit["payer_name"] == "Ndeshi Nghifindaka"
    assert (deposit["unallocated"], deposit["reservation_reference"]) == (
        "1000.00",
        res["reference"],
    )

    inv = await _issue(client, await _invoice_for(client, prop, res))
    r = await _post(
        client,
        f"/api/v1/payments/{deposit['id']}/allocations",
        {"invoice_id": inv["id"], "amount": "1000.00"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["unallocated"] == "0.00"
    # Paying at check-out against the invoice allocates up to what it owes.
    final = await _pay(client, prop, "2500.00", method="cash", invoice_id=inv["id"])
    assert (final["allocated"], final["unallocated"]) == ("2000.00", "500.00")
    m = await _money(client, inv)
    assert (m["paid"], m["balance"]) == ("3000.00", "0.00")
    assert {p["id"] for p in m["payments"]} == {deposit["id"], final["id"]}

    # Nothing more can be allocated to a settled invoice.
    r = await _post(
        client,
        f"/api/v1/payments/{final['id']}/allocations",
        {"invoice_id": inv["id"], "amount": "1.00"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "The invoice only owes 0.00."


async def test_idempotent_recording(client, factory) -> None:
    _, prop, _, _, inv = await _issued(client, factory)
    body = {
        "method": "card",
        "amount": "3000.00",
        "invoice_id": inv["id"],
        "idempotency_key": key(),
    }
    url = f"/api/v1/properties/{prop['id']}/payments"
    first = await _post(client, url, body)
    again = await _post(client, url, body)
    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]
    assert (await _money(client, inv))["paid"] == "3000.00"
    # The same key with different details is refused, not silently ignored.
    r = await _post(client, url, {**body, "amount": "10.00"})
    assert r.status_code == 409
    # Concurrent double-submits record one payment.
    body2 = {"method": "cash", "amount": "50.00", "payer_name": "Bar tab", "idempotency_key": key()}
    headers = await csrf(client)
    results = await asyncio.gather(
        *(client.post(url, json=body2, headers=headers) for _ in range(4))
    )
    assert sorted(r.status_code for r in results) == [200, 200, 200, 201]
    assert len({r.json()["id"] for r in results}) == 1


async def test_overpayment_after_credit_note_is_refunded(client, factory) -> None:
    _, prop, _, _, inv = await _issued(client, factory)
    pay = await _pay(client, prop, "3000.00", invoice_id=inv["id"])
    r = await _post(
        client,
        f"/api/v1/invoices/{inv['id']}/credit-notes",
        {
            "reason": "One night comped",
            "lines": [{"invoice_item_id": inv["items"][0]["id"], "amount": "1000.00"}],
        },
    )
    assert r.status_code == 201
    assert (await _money(client, inv))["balance"] == "-1000.00"

    url = f"/api/v1/payments/{pay['id']}/refunds"
    base = {"method": "card", "reason": "Comped night", "idempotency_key": key()}
    # More than the overpayment cannot be released from the invoice.
    r = await _post(
        client, url, {**base, "amount": "1000.01", "release_from_invoice_id": inv["id"]}
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "The invoice is only overpaid by 1000.00."
    r = await _post(
        client, url, {**base, "amount": "1000.00", "release_from_invoice_id": inv["id"]}
    )
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["allocated"], p["refunded"], p["unallocated"]) == ("2000.00", "1000.00", "0.00")
    assert (await _money(client, inv))["balance"] == "0.00"
    # Retrying the same refund does not refund twice.
    again = await _post(
        client, url, {**base, "amount": "1000.00", "release_from_invoice_id": inv["id"]}
    )
    assert again.status_code == 200 and again.json()["refunded"] == "1000.00"
    # A payment with refunds cannot be reversed.
    r = await _post(client, f"/api/v1/payments/{pay['id']}/reverse", {"reason": "Oops"})
    assert r.status_code == 409


async def test_reversal_releases_allocations_and_leaves_cash_up(client, factory) -> None:
    _, prop, _, _, inv = await _issued(client, factory)
    wrong = await _pay(client, prop, "3000.00", method="cash", invoice_id=inv["id"])
    right = await _pay(client, prop, "500.00", method="card", payer_name="Day visitor")
    r = await _post(client, f"/api/v1/payments/{wrong['id']}/reverse", {"reason": "Entered twice"})
    assert r.status_code == 200, r.text
    rev = r.json()
    assert rev["reversed_at"] and rev["unallocated"] == "0.00" and rev["allocated"] == "0.00"
    assert [a["amount"] for a in rev["allocations"]] == ["3000.00", "-3000.00"]
    assert (await _money(client, inv))["balance"] == "3000.00"
    r = await _post(client, f"/api/v1/payments/{wrong['id']}/reverse", {"reason": "Again"})
    assert r.status_code == 409

    cash = (await client.get(f"/api/v1/properties/{prop['id']}/cash-up")).json()
    assert [(t["method"], t["received"], t["count"]) for t in cash["totals"]] == [
        ("card", "500.00", 1)
    ]
    assert {p["id"] for p in cash["payments"]} == {wrong["id"], right["id"]}


async def test_cash_up_by_day_and_method(client, factory) -> None:
    _, prop, _, _, inv = await _issued(client, factory)
    from tests.test_stays import d

    await _pay(client, prop, "100.00", method="cash", received_on=d(-1), payer_name="Bar")
    await _pay(client, prop, "200.00", method="cash", payer_name="Bar")
    card = await _pay(client, prop, "300.00", method="card", payer_name="Day visitor")
    r = await _post(
        client,
        f"/api/v1/payments/{card['id']}/refunds",
        {
            "amount": "50.00",
            "method": "card",
            "reason": "Minibar charged twice",
            "idempotency_key": key(),
        },
    )
    assert r.status_code == 201, r.text
    # Money allocated to an invoice is not free to refund.
    paid = await _pay(client, prop, "100.00", method="card", invoice_id=inv["id"])
    r = await _post(
        client,
        f"/api/v1/payments/{paid['id']}/refunds",
        {"amount": "1.00", "method": "card", "reason": "Test", "idempotency_key": key()},
    )
    assert r.status_code == 409
    r = await client.get(
        f"/api/v1/properties/{prop['id']}/cash-up", params={"from": d(-1), "to": d(0)}
    )
    cash = r.json()
    assert [day["date"] for day in cash["days"]] == [d(-1), d(0)]
    totals = {(t["method"]): (t["received"], t["refunded"], t["net"]) for t in cash["totals"]}
    assert totals == {"cash": ("300.00", "0.00", "300.00"), "card": ("400.00", "50.00", "350.00")}
    r = await client.get(
        f"/api/v1/properties/{prop['id']}/cash-up", params={"from": d(0), "to": d(-1)}
    )
    assert r.status_code == 422
    # Future receipts are refused.
    r = await _post(
        client,
        f"/api/v1/properties/{prop['id']}/payments",
        {
            "method": "cash",
            "amount": "1.00",
            "received_on": d(1),
            "payer_name": "Walk-in",
            "idempotency_key": key(),
        },
    )
    assert r.status_code == 422


async def test_invoice_lock_serialises_allocations(client, factory, app_engine) -> None:
    """Deterministic race: transaction A allocates payment A to the whole invoice and stays
    open; transaction B allocates payment B to the same invoice. B must wait for A's invoice
    lock and then be refused. Without the lock B reads the old balance and over-allocates
    (verified by removing it)."""
    org, prop, _, _, inv = await _issued(client, factory)
    pa = await _pay(client, prop, "3000.00", payer_name="Company A")
    pb = await _pay(client, prop, "3000.00", payer_name="Company B")
    me = (await client.get("/api/v1/auth/me")).json()
    user_id = uuid.UUID(me["user"]["id"])

    async def session_for() -> AsyncSession:
        s = AsyncSession(app_engine, expire_on_commit=False)
        await s.begin()
        await set_tenant_context(s, user_id=user_id, organisation_id=org.id)
        return s

    async def allocate(s: AsyncSession, payment_id: str) -> object:
        payment = await s.get(Payment, uuid.UUID(payment_id))
        invoice = await s.get(Invoice, uuid.UUID(inv["id"]))
        assert payment is not None and invoice is not None
        return await service.allocate(s, payment, invoice, Decimal("3000.00"), user_id=user_id)

    a, b = await session_for(), await session_for()
    try:
        await allocate(a, pa["id"])
        b_task = asyncio.create_task(allocate(b, pb["id"]))
        await asyncio.sleep(0.5)
        assert not b_task.done(), "B should be waiting for A's invoice lock"
        await a.commit()
        with pytest.raises(service.PaymentError, match=r"only owes 0\.00"):
            await b_task
    finally:
        await a.close()
        await b.rollback()
        await b.close()
    assert (await _money(client, inv))["paid"] == "3000.00"


async def test_database_keeps_money_records(client, factory, app_engine) -> None:
    org, prop, _, _, inv = await _issued(client, factory)
    p = await _pay(client, prop, "3000.00", invoice_id=inv["id"])
    for sql in (
        "UPDATE payments SET amount = 1 WHERE id = :id",
        "DELETE FROM payments WHERE id = :id",
        "UPDATE payment_allocations SET amount = 1 WHERE payment_id = :id",
        "DELETE FROM payment_allocations WHERE payment_id = :id",
    ):
        async with app_engine.connect() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_org_id', :o, true)"), {"o": str(org.id)}
            )
            with pytest.raises(DBAPIError):
                await conn.execute(text(sql), {"id": uuid.UUID(p["id"])})
            await conn.rollback()


async def test_permissions(client, factory) -> None:
    org, prop, _, _, inv = await _issued(client, factory)
    front = await factory.user()
    await factory.member(org, front, Role.RECEPTIONIST)
    await login(client, front.email)
    p = await _pay(client, prop, "3000.00", invoice_id=inv["id"])
    r = await _post(client, f"/api/v1/payments/{p['id']}/reverse", {"reason": "Mistake"})
    assert r.status_code == 403

    keeper = await factory.user()
    await factory.member(org, keeper, Role.HOUSEKEEPING)
    await login(client, keeper.email)
    assert (await client.get(f"/api/v1/payments/{p['id']}")).status_code == 403
    assert (await client.get(f"/api/v1/properties/{prop['id']}/cash-up")).status_code == 403

    books = await factory.user()
    await factory.member(org, books, Role.ACCOUNTANT)
    await login(client, books.email)
    r = await _post(client, f"/api/v1/payments/{p['id']}/reverse", {"reason": "Mistake"})
    assert r.status_code == 200

    other = await factory.organisation("Elsewhere")
    stranger = await factory.user()
    await factory.member(other, stranger, Role.OWNER)
    await login(client, stranger.email)
    assert (await client.get(f"/api/v1/payments/{p['id']}")).status_code == 404
    assert Decimal(p["amount"]) == Decimal("3000.00")
