"""Public booking engine (ADR-0012): anonymous guests search and book one enabled property."""

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.redis import get_redis
from app.main import app
from app.modules.booking_engine.service import expire_holds
from tests.conftest import csrf
from tests.test_reservations import _post, _setup
from tests.test_stays import d

TERMS = "Free cancellation up to 7 days before arrival. Pay at the lodge."


async def _staff_find(client, prop, reference):
    rows = (
        await client.get(
            f"/api/v1/properties/{prop['id']}/reservations",
            params={"from": d(-1), "to": d(60), "include_cancelled": True},
        )
    ).json()
    return next(x for x in rows if x["reference"] == reference)


def key() -> str:
    return uuid.uuid4().hex


@pytest.fixture
async def guest_client():
    """A browser with no LodgeOS session."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def _patch(client, url, body):
    return await client.patch(url, json=body, headers=await csrf(client))


async def _online(client, factory, *, mode="request", rooms=2):
    org, prop, rt, plan, room_list = await _setup(client, factory, rooms=rooms)
    r = await _patch(client, f"/api/v1/properties/{prop['id']}", {"booking_engine_enabled": True})
    assert r.status_code == 422
    assert r.json()["detail"].startswith("Add booking terms")
    r = await _patch(
        client,
        f"/api/v1/properties/{prop['id']}",
        {"booking_engine_enabled": True, "booking_terms": TERMS, "booking_mode": mode},
    )
    assert r.status_code == 200, r.text
    r = await _patch(client, f"/api/v1/rate-plans/{plan['id']}", {"sell_online": True})
    assert r.status_code == 200, r.text
    base = f"/api/v1/public/properties/{org.slug}/{prop['slug']}"
    return org, prop, rt, plan, room_list, base


def _booking(rt, plan, check_in, check_out, **extra):
    return {
        "check_in": check_in,
        "check_out": check_out,
        "rooms": [{"room_type_id": rt["id"], "rate_plan_id": plan["id"], "adults": 2}],
        "guest": {"first_name": "Aina", "last_name": "Nghipondoka", "email": "Aina@Example.com"},
        "accept_terms": True,
        "idempotency_key": key(),
        **extra,
    }


async def test_only_enabled_properties_are_public(client, factory, guest_client) -> None:
    org, prop, *_ = await _setup(client, factory)
    url = f"/api/v1/public/properties/{org.slug}/{prop['slug']}"
    assert (await guest_client.get(url)).status_code == 404  # not enabled
    other_org, other_prop, *_ = await _setup(client, factory)
    await _patch(
        client,
        f"/api/v1/properties/{other_prop['id']}",
        {"booking_engine_enabled": True, "booking_terms": TERMS},
    )
    # The slugs must belong together: a property cannot be reached through another org.
    mixed = f"/api/v1/public/properties/{org.slug}/{other_prop['slug']}"
    assert (await guest_client.get(mixed)).status_code in (404,)
    ok = f"/api/v1/public/properties/{other_org.slug}/{other_prop['slug']}"
    r = await guest_client.get(ok)
    assert r.status_code == 200, r.text
    profile = r.json()
    assert (profile["name"], profile["booking_terms"]) == ("Epupa Camp", TERMS)
    assert [t["name"] for t in profile["room_types"]] == ["Tent"]
    assert "notes" not in str(profile) and "organisation_id" not in str(profile)
    # Archiving takes it offline.
    await _patch(client, f"/api/v1/properties/{other_prop['id']}", {"status": "archived"})
    assert (await guest_client.get(ok)).status_code == 404


async def test_offers_show_online_rates_and_availability(client, factory, guest_client) -> None:
    _, prop, rt, _, _, base = await _online(client, factory)
    private = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/rate-plans",
            {"name": "Namib Mining corporate", "code": "CORP", "kind": "corporate"},
        )
    ).json()
    await client.put(
        f"/api/v1/rate-plans/{private['id']}/prices/{rt['id']}",
        json={"base_price": "500.00"},
        headers=await csrf(client),
    )
    r = await guest_client.get(f"{base}/offers", params={"check_in": d(10), "check_out": d(12)})
    assert r.status_code == 200, r.text
    [tent] = r.json()
    assert tent["available"] == 2
    # Only the plan marked for online sale; the corporate rate stays private.
    assert [(o["name"], o["total"], o["nights"]) for o in tent["offers"]] == [
        ("Standard", "2000.00", 2)
    ]
    # Too many guests for the room type: not offered.
    r = await guest_client.get(
        f"{base}/offers", params={"check_in": d(10), "check_out": d(12), "adults": 3}
    )
    assert r.json() == []
    # Outside the booking window.
    r = await guest_client.get(f"{base}/offers", params={"check_in": d(-1), "check_out": d(1)})
    assert r.status_code == 422


async def test_request_booking_holds_rooms_and_queues_email(client, factory, guest_client) -> None:
    _, prop, rt, plan, _, base = await _online(client, factory)
    headers = await csrf(guest_client)
    body = _booking(rt, plan, d(10), d(12), special_requests="Late arrival, around 21:00")
    r = await guest_client.post(f"{base}/bookings", json=body, headers=headers)
    assert r.status_code == 201, r.text
    b = r.json()
    assert (b["status"], b["total"], b["email"], b["guest_name"]) == (
        "provisional",
        "2000.00",
        "aina@example.com",
        "Aina Nghipondoka",
    )
    assert b["hold_expires_at"] is not None
    # A double submit returns the same booking.
    again = await guest_client.post(f"{base}/bookings", json=body, headers=headers)
    assert (again.status_code, again.json()["reference"]) == (200, b["reference"])

    # Staff see it as a website booking with the guest's request, and the email queued.
    res = await _staff_find(client, prop, b["reference"])
    detail = (await client.get(f"/api/v1/reservations/{res['id']}")).json()
    assert (detail["source"], detail["notes"]) == (
        "website",
        "Guest request: Late arrival, around 21:00",
    )
    emails = (
        await client.get(
            "/api/v1/notifications", params={"subject_type": "reservation", "subject_id": res["id"]}
        )
    ).json()
    assert [(e["kind"], e["recipient"]) for e in emails] == [
        ("booking_confirmation", "aina@example.com")
    ]
    assert emails[0]["title"].startswith(f"Booking request {b['reference']}")
    offers = (
        await guest_client.get(f"{base}/offers", params={"check_in": d(10), "check_out": d(12)})
    ).json()
    assert offers[0]["available"] == 1  # the request holds a room


async def test_instant_mode_confirms(client, factory, guest_client) -> None:
    _, _, rt, plan, _, base = await _online(client, factory, mode="instant")
    r = await guest_client.post(
        f"{base}/bookings", json=_booking(rt, plan, d(5), d(6)), headers=await csrf(guest_client)
    )
    assert r.status_code == 201, r.text
    assert (r.json()["status"], r.json()["hold_expires_at"]) == ("confirmed", None)


async def test_refusals(client, factory, guest_client) -> None:
    _, _, rt, plan, _, base = await _online(client, factory, rooms=1)
    headers = await csrf(guest_client)
    url = f"{base}/bookings"
    r = await guest_client.post(
        url, json=_booking(rt, plan, d(3), d(4), website="http://spam"), headers=headers
    )
    assert r.status_code == 422
    r = await guest_client.post(
        url, json=_booking(rt, plan, d(3), d(4), accept_terms=False), headers=headers
    )
    assert r.json()["detail"] == "Please accept the booking terms."
    r = await guest_client.post(url, json=_booking(rt, plan, d(3), d(40)), headers=headers)
    assert r.status_code == 422 and "30 nights" in r.json()["detail"]
    await get_redis().flushdb()  # the refusals above count towards the hourly limit
    # A private plan cannot be booked by guessing its id.
    await _patch(client, f"/api/v1/rate-plans/{plan['id']}", {"sell_online": False})
    r = await guest_client.post(url, json=_booking(rt, plan, d(3), d(4)), headers=headers)
    assert r.json()["detail"] == "That rate is not available online."
    await _patch(client, f"/api/v1/rate-plans/{plan['id']}", {"sell_online": True})
    await get_redis().flushdb()
    # The last room goes; the next guest is told plainly.
    assert (
        await guest_client.post(url, json=_booking(rt, plan, d(3), d(4)), headers=headers)
    ).status_code == 201
    r = await guest_client.post(url, json=_booking(rt, plan, d(3), d(4)), headers=headers)
    assert r.status_code == 409
    assert r.json()["detail"] == "Sorry, those rooms were just taken. Please search again."
    # Five booking attempts an hour per address: two above, three here, the sixth refused.
    for i in range(3):
        await guest_client.post(url, json=_booking(rt, plan, d(20 + i), d(21 + i)), headers=headers)
    r = await guest_client.post(url, json=_booking(rt, plan, d(30), d(31)), headers=headers)
    assert r.status_code == 429


async def test_expired_requests_are_cancelled_and_free_the_room(
    client, factory, guest_client, app_engine: AsyncEngine
) -> None:
    _, prop, rt, plan, _, base = await _online(client, factory, rooms=1)
    headers = await csrf(guest_client)
    b = (
        await guest_client.post(
            f"{base}/bookings", json=_booking(rt, plan, d(7), d(9)), headers=headers
        )
    ).json()
    sm = async_sessionmaker(app_engine, expire_on_commit=False)
    assert await expire_holds(sm) == 0  # not yet due
    await factory.execute(
        "UPDATE reservations SET hold_expires_at = now() - interval '1 minute'"
        " WHERE reference = :r",
        r=b["reference"],
    )
    assert await expire_holds(sm) == 1
    assert await expire_holds(sm) == 0
    res = await _staff_find(client, prop, b["reference"])
    detail = (await client.get(f"/api/v1/reservations/{res['id']}")).json()
    assert (detail["status"], detail["cancellation_reason"]) == (
        "cancelled",
        "Request not confirmed within 48 hours.",
    )
    offers = (
        await guest_client.get(f"{base}/offers", params={"check_in": d(7), "check_out": d(9)})
    ).json()
    assert offers[0]["available"] == 1

    # A request confirmed by staff is never expired.
    b2 = (
        await guest_client.post(
            f"{base}/bookings", json=_booking(rt, plan, d(7), d(9)), headers=headers
        )
    ).json()
    res2 = await _staff_find(client, prop, b2["reference"])
    await _post(client, f"/api/v1/reservations/{res2['id']}/confirm", {})
    await factory.execute(
        "UPDATE reservations SET hold_expires_at = now() - interval '1 minute'"
        " WHERE reference = :r",
        r=b2["reference"],
    )
    assert await expire_holds(sm) == 0
