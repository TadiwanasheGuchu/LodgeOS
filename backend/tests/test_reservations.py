"""Reservations: availability, concurrency, physical allocation, cancellation, snapshots."""

import asyncio
import uuid
from datetime import date

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.db import set_tenant_context
from app.main import app
from app.modules.guests.models import Guest
from app.modules.organisations.models import Role
from app.modules.properties.models import Property
from app.modules.reservations import service
from app.modules.reservations.models import ReservationStatus
from tests.conftest import Factory, csrf, login


async def _post(client, url, body):
    return await client.post(url, json=body, headers=await csrf(client))


async def _setup(client, factory: Factory, rooms: int = 2):
    """A property with one room type of ``rooms`` rooms, priced at 1000.00 a night."""
    org = await factory.organisation("Kaokoland Lodges")
    owner = await factory.user()
    await factory.member(org, owner, Role.OWNER)
    await login(client, owner.email)
    prop = (
        await _post(client, "/api/v1/properties", {"name": "Epupa Camp", "property_type": "lodge"})
    ).json()
    rt = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/room-types",
            {
                "name": "Tent",
                "code": "TNT",
                "base_occupancy": 2,
                "max_occupancy": 2,
                "max_adults": 2,
            },
        )
    ).json()
    numbers = [str(i) for i in range(1, rooms + 1)]
    room_list = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/rooms/bulk",
            {"numbers": numbers, "room_type_id": rt["id"]},
        )
    ).json()
    plan = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/rate-plans",
            {"name": "Standard", "code": "STD"},
        )
    ).json()
    await client.put(
        f"/api/v1/rate-plans/{plan['id']}/prices/{rt['id']}",
        json={"base_price": "1000.00"},
        headers=await csrf(client),
    )
    return org, prop, rt, plan, room_list


def _booking(
    rt, plan, check_in="2026-12-01", check_out="2026-12-04", room_id=None, last="Nghifindaka"
):
    room = {"room_type_id": rt["id"], "rate_plan_id": plan["id"], "adults": 2}
    if room_id:
        room["room_id"] = room_id
    return {
        "check_in": check_in,
        "check_out": check_out,
        "guest": {"first_name": "Ndeshi", "last_name": last, "email": "ndeshi@example.com"},
        "rooms": [room],
        "source": "phone",
    }


async def test_booking_is_priced_and_referenced(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    r = await _post(client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan))
    assert r.status_code == 201, r.text
    res = r.json()
    assert res["reference"].startswith("LOS-") and len(res["reference"]) == 10
    assert res["status"] == "confirmed"
    assert (res["nights"], res["room_count"], res["total_amount"], res["currency"]) == (
        3,
        1,
        "3000.00",
        "NAD",
    )
    snap = res["rooms"][0]["price_snapshot"]
    assert [n["amount"] for n in snap["nights"]] == ["1000.00"] * 3
    assert res["history"][0]["to_status"] == "confirmed"
    assert res["guest"]["email"] == "ndeshi@example.com"


async def test_room_type_cannot_be_oversold(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory, rooms=2)
    url = f"/api/v1/properties/{prop['id']}/reservations"
    assert (await _post(client, url, _booking(rt, plan))).status_code == 201
    assert (
        await _post(client, url, _booking(rt, plan, "2026-12-02", "2026-12-03"))
    ).status_code == 201
    r = await _post(client, url, _booking(rt, plan, "2026-11-30", "2026-12-03"))
    assert r.status_code == 409
    assert r.json()["detail"] == "Only 0 Tent rooms are free on 2026-12-02."
    # The night before and after are still bookable.
    assert (
        await _post(client, url, _booking(rt, plan, "2026-11-30", "2026-12-01"))
    ).status_code == 201

    avail = (
        await client.get(
            f"/api/v1/properties/{prop['id']}/availability",
            params={"check_in": "2026-12-01", "check_out": "2026-12-04"},
        )
    ).json()
    assert [n["free"] for n in avail[0]["nights"]] == [1, 0, 1]
    assert avail[0]["free"] == 0


async def test_concurrent_bookings_for_the_last_room(client, factory) -> None:
    """Eight receptionists book the only room at the same moment: exactly one succeeds."""
    _, prop, rt, plan, _ = await _setup(client, factory, rooms=1)
    headers = await csrf(client)

    async def attempt(i: int) -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", cookies=client.cookies
        ) as c:
            r = await c.post(
                f"/api/v1/properties/{prop['id']}/reservations",
                json=_booking(rt, plan, last=f"Guest{i}"),
                headers=headers,
            )
            return r.status_code

    results = sorted(await asyncio.gather(*(attempt(i) for i in range(8))))
    assert results == [201] + [409] * 7


async def test_inventory_lock_serialises_overlapping_transactions(
    app_engine: AsyncEngine, client, factory
) -> None:
    """Deterministic race: transaction A books the last room and stays open; transaction B
    books the same room type meanwhile. B must wait for A's lock and then be refused.
    Without the lock B would count no bookings and oversell (verified by removing it)."""
    org, prop_json, rt, plan, _ = await _setup(client, factory, rooms=1)
    me = (await client.get("/api/v1/auth/me")).json()

    async def session_for():  # a separate connection acting as this organisation
        s = AsyncSession(app_engine, expire_on_commit=False)
        await s.begin()
        await set_tenant_context(s, user_id=uuid.UUID(me["user"]["id"]), organisation_id=org.id)
        return s

    async def book(s):
        prop = await s.get(Property, uuid.UUID(prop_json["id"]))
        guest = Guest(organisation_id=org.id, first_name="A", last_name="B")
        s.add(guest)
        await s.flush()
        return await service.create_reservation(
            s,
            prop=prop,
            guest_id=guest.id,
            check_in=date(2026, 12, 1),
            check_out=date(2026, 12, 3),
            rooms=[service.RoomRequest(uuid.UUID(rt["id"]), uuid.UUID(plan["id"]), 2, 0)],
            status=ReservationStatus.CONFIRMED,
            source="phone",
            notes=None,
            user_id=uuid.UUID(me["user"]["id"]),
        )

    a, b = await session_for(), await session_for()
    try:
        await book(a)  # A holds the room-type lock until it commits
        b_task = asyncio.create_task(book(b))
        await asyncio.sleep(0.5)
        assert not b_task.done(), "B should be waiting for A's lock"
        await a.commit()
        with pytest.raises(service.BookingError, match="Only 0 Tent rooms are free"):
            await b_task
    finally:
        await a.close()
        await b.rollback()
        await b.close()


async def test_physical_room_cannot_be_double_booked(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=3)
    url = f"/api/v1/properties/{prop['id']}/reservations"
    room1 = rooms[0]["id"]
    assert (await _post(client, url, _booking(rt, plan, room_id=room1))).status_code == 201
    r = await _post(client, url, _booking(rt, plan, "2026-12-03", "2026-12-05", room_id=room1))
    assert r.status_code == 409
    assert r.json()["detail"] == "That room is already booked for some of these nights."
    # Departure day = next arrival day is fine.
    assert (
        await _post(client, url, _booking(rt, plan, "2026-12-04", "2026-12-06", room_id=room1))
    ).status_code == 201


async def test_database_rejects_overlapping_allocation(
    app_engine: AsyncEngine, client, factory
) -> None:
    """Even bypassing the API, the exclusion constraint holds."""
    org, prop, rt, plan, rooms = await _setup(client, factory)
    res = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/reservations",
            _booking(rt, plan, room_id=rooms[0]["id"]),
        )
    ).json()
    async with app_engine.connect() as conn:
        tx = await conn.begin()
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"), {"o": str(org.id)}
        )
        with pytest.raises(DBAPIError, match="ex_reservation_rooms_no_double_booking"):
            await conn.execute(
                text(
                    "INSERT INTO reservation_rooms (id, organisation_id, property_id,"
                    " reservation_id, room_type_id, room_id, rate_plan_id, check_in, check_out,"
                    " status, adults, children, total_amount, tax_amount, price_snapshot)"
                    " VALUES (:id, :org, :prop, :res, :rt, :room, :plan, '2026-12-02',"
                    " '2026-12-03', 'confirmed', 1, 0, 0, 0, '{}')"
                ),
                {
                    "id": uuid.uuid4(),
                    "org": org.id,
                    "prop": prop["id"],
                    "res": res["id"],
                    "rt": rt["id"],
                    "room": rooms[0]["id"],
                    "plan": plan["id"],
                },
            )
        await tx.rollback()
    async with app_engine.connect() as conn:
        tx = await conn.begin()
        with pytest.raises(DBAPIError, match="permission denied"):
            await conn.execute(text("DELETE FROM reservations"))
        await tx.rollback()


async def test_cancellation_needs_a_reason_and_frees_the_room(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory, rooms=1)
    url = f"/api/v1/properties/{prop['id']}/reservations"
    res = (await _post(client, url, _booking(rt, plan))).json()
    assert (await _post(client, url, _booking(rt, plan))).status_code == 409

    cancel = f"/api/v1/reservations/{res['id']}/cancel"
    assert (await _post(client, cancel, {})).status_code == 422
    r = await _post(client, cancel, {"reason": "Guest's flight was cancelled"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "cancelled"
    assert body["cancellation_reason"] == "Guest's flight was cancelled"
    assert [h["to_status"] for h in body["history"]] == ["confirmed", "cancelled"]

    assert (await _post(client, url, _booking(rt, plan))).status_code == 201  # room free again
    assert (
        await _post(client, cancel, {"reason": "again"})
    ).status_code == 409  # already cancelled
    hidden = (await client.get(url, params={"from": "2026-12-01", "to": "2026-12-04"})).json()
    assert [x["status"] for x in hidden] == ["confirmed"]


async def test_provisional_then_confirmed(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    res = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/reservations",
            _booking(rt, plan) | {"status": "provisional"},
        )
    ).json()
    assert res["status"] == "provisional"
    r = await _post(client, f"/api/v1/reservations/{res['id']}/confirm", {})
    assert r.json()["status"] == "confirmed"
    assert [h["to_status"] for h in r.json()["history"]] == ["provisional", "confirmed"]
    assert (await _post(client, f"/api/v1/reservations/{res['id']}/confirm", {})).status_code == 409


async def test_price_is_frozen_when_rates_change(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    res = (
        await _post(client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan))
    ).json()
    await client.put(
        f"/api/v1/rate-plans/{plan['id']}/prices/{rt['id']}",
        json={"base_price": "2500.00"},
        headers=await csrf(client),
    )
    again = (await client.get(f"/api/v1/reservations/{res['id']}")).json()
    assert again["total_amount"] == "3000.00"
    assert again["rooms"][0]["price_snapshot"] == res["rooms"][0]["price_snapshot"]


async def test_out_of_order_rooms_are_not_sold(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=1)
    await _post(
        client,
        f"/api/v1/rooms/{rooms[0]['id']}/maintenance",
        {"maintenance_status": "out_of_order", "reason": "Storm damage"},
    )
    r = await _post(client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan))
    assert r.status_code == 409
    assert "Only 0" in r.json()["detail"]


async def test_booking_validation(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    url = f"/api/v1/properties/{prop['id']}/reservations"
    bad_dates = _booking(rt, plan, "2026-12-04", "2026-12-04")
    assert (await _post(client, url, bad_dates)).status_code == 422
    too_many = _booking(rt, plan)
    too_many["rooms"][0]["adults"] = 3
    r = await _post(client, url, too_many)
    assert r.status_code == 422
    assert r.json()["detail"] == "Tent: This room type takes at most 2 adults."
    no_guest = _booking(rt, plan)
    del no_guest["guest"]
    assert (await _post(client, url, no_guest)).status_code == 422


async def test_returning_guest_is_found_and_reused(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    url = f"/api/v1/properties/{prop['id']}/reservations"
    first = (await _post(client, url, _booking(rt, plan))).json()
    found = (await client.get("/api/v1/guests", params={"q": "nghifin"})).json()
    assert [g["id"] for g in found] == [first["guest"]["id"]]
    body = _booking(rt, plan, "2027-01-10", "2027-01-12")
    del body["guest"]
    body["guest_id"] = first["guest"]["id"]
    second = (await _post(client, url, body)).json()
    assert second["guest_id"] == first["guest_id"]


async def test_reservation_permissions(client, factory) -> None:
    org, prop, rt, plan, _ = await _setup(client, factory)
    res = (
        await _post(client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan))
    ).json()
    await client.post("/api/v1/auth/logout", headers=await csrf(client))

    hk = await factory.user()
    await factory.member(org, hk, Role.HOUSEKEEPING)
    await login(client, hk.email)
    assert (await client.get(f"/api/v1/reservations/{res['id']}")).status_code == 403  # guest data
    assert (await client.get("/api/v1/guests", params={"q": "nde"})).status_code == 403
    await client.post("/api/v1/auth/logout", headers=await csrf(client))

    acc = await factory.user()
    await factory.member(org, acc, Role.ACCOUNTANT)
    await login(client, acc.email)
    assert (await client.get(f"/api/v1/reservations/{res['id']}")).status_code == 200
    assert (
        await _post(client, f"/api/v1/reservations/{res['id']}/cancel", {"reason": "nope"})
    ).status_code == 403
    await client.post("/api/v1/auth/logout", headers=await csrf(client))

    other = await factory.organisation("Other")
    u = await factory.user()
    await factory.member(other, u, Role.OWNER)
    await login(client, u.email)
    assert (await client.get(f"/api/v1/reservations/{res['id']}")).status_code == 404
    assert (await client.get("/api/v1/guests", params={"q": "nde"})).json() == []
