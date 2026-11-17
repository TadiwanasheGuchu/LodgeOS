"""Room allocation, calendar and today's arrivals and departures."""

from datetime import date, timedelta

from app.modules.organisations.models import Role
from tests.conftest import csrf, login
from tests.test_reservations import _booking, _post, _setup


async def test_assign_move_and_unassign(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=3)
    url = f"/api/v1/properties/{prop['id']}/reservations"
    a = (await _post(client, url, _booking(rt, plan))).json()
    b = (await _post(client, url, _booking(rt, plan, "2026-12-03", "2026-12-05"))).json()
    rr_a, rr_b = a["rooms"][0]["id"], b["rooms"][0]["id"]

    free = (await client.get(f"/api/v1/reservation-rooms/{rr_a}/free-rooms")).json()
    assert [r["number"] for r in free] == ["1", "2", "3"]
    r = await _post(client, f"/api/v1/reservation-rooms/{rr_a}/assign", {"room_id": rooms[0]["id"]})
    assert r.status_code == 200
    assert r.json()["rooms"][0]["room_number"] == "1"

    # Booking B overlaps on the night of 3 December: room 1 is no longer offered or accepted.
    free_b = (await client.get(f"/api/v1/reservation-rooms/{rr_b}/free-rooms")).json()
    assert [r["number"] for r in free_b] == ["2", "3"]
    r = await _post(client, f"/api/v1/reservation-rooms/{rr_b}/assign", {"room_id": rooms[0]["id"]})
    assert r.status_code == 409
    assert r.json()["detail"] == "That room is already booked for some of these nights."

    # Move A to room 2, then B can take room 1; then unassign A.
    assert (
        await _post(client, f"/api/v1/reservation-rooms/{rr_a}/assign", {"room_id": rooms[1]["id"]})
    ).status_code == 200
    assert (
        await _post(client, f"/api/v1/reservation-rooms/{rr_b}/assign", {"room_id": rooms[0]["id"]})
    ).status_code == 200
    r = await _post(client, f"/api/v1/reservation-rooms/{rr_a}/assign", {"room_id": None})
    assert r.json()["rooms"][0]["room_number"] is None

    actions = [
        i["action"] for i in (await client.get("/api/v1/organisation/audit-logs")).json()["items"]
    ]
    assert actions.count("reservation.room_assigned") == 4


async def test_assignment_rules(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=2)
    other_rt = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/room-types",
            {
                "name": "Suite",
                "code": "STE",
                "base_occupancy": 2,
                "max_occupancy": 2,
                "max_adults": 2,
            },
        )
    ).json()
    suite = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/rooms",
            {"number": "S1", "room_type_id": other_rt["id"]},
        )
    ).json()
    res = (
        await _post(client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan))
    ).json()
    rr = res["rooms"][0]["id"]
    assert (
        await _post(client, f"/api/v1/reservation-rooms/{rr}/assign", {"room_id": suite["id"]})
    ).status_code == 422

    await _post(
        client,
        f"/api/v1/rooms/{rooms[1]['id']}/maintenance",
        {"maintenance_status": "out_of_order", "reason": "Roof"},
    )
    assert (
        await _post(client, f"/api/v1/reservation-rooms/{rr}/assign", {"room_id": rooms[1]["id"]})
    ).status_code == 409
    assert [
        r["number"] for r in (await client.get(f"/api/v1/reservation-rooms/{rr}/free-rooms")).json()
    ] == ["1"]

    await _post(client, f"/api/v1/reservations/{res['id']}/cancel", {"reason": "Changed plans"})
    assert (
        await _post(client, f"/api/v1/reservation-rooms/{rr}/assign", {"room_id": rooms[0]["id"]})
    ).status_code == 409


async def test_calendar(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=2)
    url = f"/api/v1/properties/{prop['id']}/reservations"
    a = (await _post(client, url, _booking(rt, plan, room_id=rooms[1]["id"]))).json()
    b = (await _post(client, url, _booking(rt, plan, "2026-12-10", "2026-12-12"))).json()
    cancelled = (await _post(client, url, _booking(rt, plan, "2026-12-05", "2026-12-06"))).json()
    await _post(
        client, f"/api/v1/reservations/{cancelled['id']}/cancel", {"reason": "No longer needed"}
    )

    cal = (
        await client.get(
            f"/api/v1/properties/{prop['id']}/calendar", params={"start": "2026-11-30", "days": 14}
        )
    ).json()
    assert [r["number"] for r in cal["rooms"]] == ["1", "2"]
    stays = {s["reference"]: s for s in cal["stays"]}
    assert set(stays) == {a["reference"], b["reference"]}  # cancelled stays are not shown
    assert stays[a["reference"]]["room_id"] == rooms[1]["id"]
    assert stays[b["reference"]]["room_id"] is None
    assert (
        await client.get(
            f"/api/v1/properties/{prop['id']}/calendar", params={"start": "2026-11-30", "days": 40}
        )
    ).status_code == 422


async def test_today(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory, rooms=2)
    # Africa/Windhoek; the endpoint uses the property's own date.
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Africa/Windhoek")).date()
    url = f"/api/v1/properties/{prop['id']}/reservations"
    arriving = (
        await _post(client, url, _booking(rt, plan, str(today), str(today + timedelta(days=2))))
    ).json()
    leaving = (
        await _post(client, url, _booking(rt, plan, str(today - timedelta(days=2)), str(today)))
    ).json()
    data = (await client.get(f"/api/v1/properties/{prop['id']}/today")).json()
    assert data["date"] == str(today)
    assert [r["reference"] for r in data["arrivals"]] == [arriving["reference"]]
    assert [r["reference"] for r in data["departures"]] == [leaving["reference"]]
    assert data["unassigned_arrivals"] == 1
    assert date.fromisoformat(data["date"]) == today


async def test_allocation_permissions(client, factory) -> None:
    org, prop, rt, plan, rooms = await _setup(client, factory)
    res = (
        await _post(client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan))
    ).json()
    rr = res["rooms"][0]["id"]
    await client.post("/api/v1/auth/logout", headers=await csrf(client))
    acc = await factory.user()
    await factory.member(org, acc, Role.ACCOUNTANT)
    await login(client, acc.email)
    assert (
        await client.get(
            f"/api/v1/properties/{prop['id']}/calendar", params={"start": "2026-12-01"}
        )
    ).status_code == 200
    assert (
        await _post(client, f"/api/v1/reservation-rooms/{rr}/assign", {"room_id": rooms[0]["id"]})
    ).status_code == 403
    await client.post("/api/v1/auth/logout", headers=await csrf(client))
    hk = await factory.user()
    await factory.member(org, hk, Role.HOUSEKEEPING)
    await login(client, hk.email)
    assert (
        await client.get(
            f"/api/v1/properties/{prop['id']}/calendar", params={"start": "2026-12-01"}
        )
    ).status_code == 403
    assert (await client.get(f"/api/v1/properties/{prop['id']}/today")).status_code == 403
