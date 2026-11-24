"""Guest portal through secret links (ADR-0013)."""

import uuid

import httpx
import pytest

from app.core.security import hash_token
from app.main import app
from app.modules.organisations.models import Role
from tests.conftest import csrf, login
from tests.test_invoices import _invoice_for, _issue
from tests.test_reservations import _booking, _post, _setup


@pytest.fixture
async def guest_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


def _token(url: str) -> str:
    assert "/stay/" in url
    return url.rsplit("/stay/", 1)[1]


async def _booked_with_link(client, factory):
    org, prop, rt, plan, _ = await _setup(client, factory)
    res = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/reservations",
            _booking(rt, plan, "2027-03-10", "2027-03-12"),
        )
    ).json()
    r = await _post(client, f"/api/v1/reservations/{res['id']}/guest-links", {})
    assert r.status_code == 201, r.text
    return org, prop, res, r.json()


async def test_guest_sees_only_their_booking(client, factory, guest_client) -> None:
    _, prop, res, link = await _booked_with_link(client, factory)
    assert link["url"].startswith("http://localhost:3000/stay/")
    assert link["expires_at"].startswith("2027-04-11")  # 30 days after check-out
    inv = await _issue(client, await _invoice_for(client, prop, res))
    await _post(
        client,
        f"/api/v1/properties/{prop['id']}/payments",
        {
            "method": "card",
            "amount": "500.00",
            "invoice_id": inv["id"],
            "idempotency_key": uuid.uuid4().hex,
        },
    )

    r = await guest_client.get(f"/api/v1/stay/{_token(link['url'])}")
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["reference"], b["guest_name"], b["total"], b["nights"]) == (
        res["reference"],
        "Ndeshi Nghifindaka",
        "2000.00",
        2,
    )
    assert b["property"]["name"] == "Epupa Camp"
    assert [(i["number"], i["paid"], i["balance"]) for i in b["invoices"]] == [
        ("INV-000001", "500.00", "1500.00")
    ]
    assert b["paid"] == "500.00" and b["can_update"] is True
    # No staff data, ids or other guests.
    text = r.text
    assert "notes" not in text and "organisation_id" not in text and res["id"] not in text


async def test_bad_revoked_and_expired_links(client, factory, guest_client, owner_engine) -> None:
    _, _, res, link = await _booked_with_link(client, factory)
    token = _token(link["url"])
    for bad in ("x", "a" * 43, token[:-1] + ("A" if token[-1] != "A" else "B")):
        r = await guest_client.get(f"/api/v1/stay/{bad}")
        assert r.status_code == 404
    assert (
        r.json()["detail"] == "This link has expired or was withdrawn. Please contact the property."
    )

    second = (await _post(client, f"/api/v1/reservations/{res['id']}/guest-links", {})).json()
    r = await _post(client, f"/api/v1/reservations/{res['id']}/guest-links/revoke", {})
    assert r.json()["revoked"] == 2
    for t in (token, _token(second["url"])):
        assert (await guest_client.get(f"/api/v1/stay/{t}")).status_code == 404

    third = _token(
        (await _post(client, f"/api/v1/reservations/{res['id']}/guest-links", {})).json()["url"]
    )
    assert (await guest_client.get(f"/api/v1/stay/{third}")).status_code == 200
    from sqlalchemy import text

    async with owner_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE guest_access_tokens SET expires_at = now() - interval '1 second'"
                " WHERE token_hash = :h"
            ),
            {"h": hash_token(third)},
        )
    assert (await guest_client.get(f"/api/v1/stay/{third}")).status_code == 404


async def test_tokens_are_stored_hashed(client, factory, owner_engine) -> None:
    _, _, _, link = await _booked_with_link(client, factory)
    from sqlalchemy import text

    async with owner_engine.connect() as conn:
        rows = (await conn.execute(text("SELECT token_hash FROM guest_access_tokens"))).all()
    token = _token(link["url"])
    assert [bytes(r[0]) for r in rows] == [hash_token(token)]
    assert token.encode() not in bytes(rows[0][0])


async def test_guest_updates_reach_staff(client, factory, guest_client) -> None:
    _, _, res, link = await _booked_with_link(client, factory)
    base = f"/api/v1/stay/{_token(link['url'])}"
    headers = await csrf(guest_client)
    r = await guest_client.post(
        f"{base}/arrival",
        json={"arrival_time": "21:30", "message": "Flight lands at 19:00 in Windhoek"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert (r.json()["arrival_time"], r.json()["message"]) == (
        "21:30",
        "Flight lands at 19:00 in Windhoek",
    )
    r = await guest_client.post(f"{base}/arrival", json={"arrival_time": "25:00"}, headers=headers)
    assert r.status_code == 422
    r = await guest_client.post(
        f"{base}/cancellation-request", json={"reason": "Flight cancelled"}, headers=headers
    )
    assert r.json()["cancellation_requested"] is True

    detail = (await client.get(f"/api/v1/reservations/{res['id']}")).json()
    assert (detail["guest_arrival_time"], detail["guest_message"]) == (
        "21:30",
        "Flight lands at 19:00 in Windhoek",
    )
    assert detail["cancellation_request_reason"] == "Flight cancelled"
    assert detail["status"] == "confirmed"  # a request, not a cancellation
    r = await _post(client, f"/api/v1/reservations/{res['id']}/cancellation-request/dismiss", {})
    assert r.status_code == 204
    assert (await client.get(f"/api/v1/reservations/{res['id']}")).json()[
        "cancellation_requested_at"
    ] is None

    # Once cancelled, the guest can still look but no longer change anything.
    await _post(client, f"/api/v1/reservations/{res['id']}/cancel", {"reason": "Guest asked"})
    b = (await guest_client.get(base)).json()
    assert (b["status"], b["can_update"]) == ("cancelled", False)
    r = await guest_client.post(f"{base}/arrival", json={"arrival_time": "10:00"}, headers=headers)
    assert r.status_code == 409


async def test_confirmation_email_carries_a_working_link(client, factory, guest_client) -> None:
    _, _, res, _ = await _booked_with_link(client, factory)
    r = await _post(
        client,
        f"/api/v1/reservations/{res['id']}/email-confirmation",
        {"idempotency_key": uuid.uuid4().hex},
    )
    body = r.json()["body_text"]
    line = next(x for x in body.splitlines() if x.startswith("View or update your booking: "))
    url = line.split(": ", 1)[1]
    assert (await guest_client.get(f"/api/v1/stay/{_token(url)}")).status_code == 200


async def test_only_front_desk_manages_links(client, factory) -> None:
    org, _, res, _ = await _booked_with_link(client, factory)
    keeper = await factory.user()
    await factory.member(org, keeper, Role.HOUSEKEEPING)
    await login(client, keeper.email)
    r = await _post(client, f"/api/v1/reservations/{res['id']}/guest-links", {})
    assert r.status_code == 403
    other = await factory.organisation("Elsewhere")
    stranger = await factory.user()
    await factory.member(other, stranger, Role.OWNER)
    await login(client, stranger.email)
    assert (
        await _post(client, f"/api/v1/reservations/{res['id']}/guest-links", {})
    ).status_code == 404
