"""Check-in, check-out, no-shows, date changes and guest edits."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.modules.organisations.models import Role
from tests.conftest import csrf, login
from tests.test_reservations import _booking, _post, _setup

TODAY = datetime.now(ZoneInfo("Africa/Windhoek")).date()


def d(days: int) -> str:
    return str(TODAY + timedelta(days=days))


async def _patch(client, url, body):
    return await client.patch(url, json=body, headers=await csrf(client))


async def _book(client, prop, rt, plan, start: int, end: int, room_id=None):
    r = await _post(
        client,
        f"/api/v1/properties/{prop['id']}/reservations",
        _booking(rt, plan, d(start), d(end), room_id=room_id),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_check_in_and_out_hand_room_to_housekeeping(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory)
    res = await _book(client, prop, rt, plan, 0, 2)

    r = await _post(client, f"/api/v1/reservations/{res['id']}/check-in", {})
    assert r.status_code == 409
    assert r.json()["detail"] == "Assign a room to every booked room before check-in."

    await _post(
        client,
        f"/api/v1/reservation-rooms/{res['rooms'][0]['id']}/assign",
        {"room_id": rooms[0]["id"]},
    )
    await _post(
        client, f"/api/v1/rooms/{rooms[0]['id']}/housekeeping", {"housekeeping_status": "inspected"}
    )
    r = await _post(client, f"/api/v1/reservations/{res['id']}/check-in", {})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "checked_in"
    # A checked-in booking can no longer be cancelled.
    assert (
        await _post(client, f"/api/v1/reservations/{res['id']}/cancel", {"reason": "Oops"})
    ).status_code == 409

    r = await _post(client, f"/api/v1/reservations/{res['id']}/check-out", {})
    assert r.json()["status"] == "checked_out"
    assert [h["to_status"] for h in r.json()["history"]] == [
        "confirmed",
        "checked_in",
        "checked_out",
    ]
    room = next(
        x
        for x in (await client.get(f"/api/v1/properties/{prop['id']}/rooms")).json()
        if x["id"] == rooms[0]["id"]
    )
    assert room["housekeeping_status"] == "dirty"

    # Checking out early frees the remaining night for new bookings.
    assert (
        len(
            (
                await client.get(
                    f"/api/v1/properties/{prop['id']}/calendar", params={"start": d(0)}
                )
            ).json()["stays"]
        )
        == 0
    )


async def test_check_in_date_rules(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory)
    future = await _book(client, prop, rt, plan, 3, 5, room_id=rooms[0]["id"])
    r = await _post(client, f"/api/v1/reservations/{future['id']}/check-in", {})
    assert r.status_code == 409
    assert r.json()["detail"] == f"Check-in opens on {d(3)}."
    assert (
        await _post(client, f"/api/v1/reservations/{future['id']}/no-show", {})
    ).status_code == 409

    provisional = await _post(
        client,
        f"/api/v1/properties/{prop['id']}/reservations",
        _booking(rt, plan, d(0), d(1), room_id=rooms[1]["id"]) | {"status": "provisional"},
    )
    assert (
        await _post(client, f"/api/v1/reservations/{provisional.json()['id']}/check-in", {})
    ).status_code == 409


async def test_no_show_frees_inventory(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory, rooms=1)
    res = await _book(client, prop, rt, plan, 0, 2)
    r = await _post(client, f"/api/v1/reservations/{res['id']}/no-show", {})
    assert r.json()["status"] == "no_show"
    assert (
        await _post(
            client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan, d(0), d(2))
        )
    ).status_code == 201


async def test_out_of_order_room_blocks_check_in(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory)
    res = await _book(client, prop, rt, plan, 0, 1, room_id=rooms[0]["id"])
    await _post(
        client,
        f"/api/v1/rooms/{rooms[0]['id']}/maintenance",
        {"maintenance_status": "out_of_order", "reason": "Leak"},
    )
    r = await _post(client, f"/api/v1/reservations/{res['id']}/check-in", {})
    assert r.status_code == 409
    assert "out of order" in r.json()["detail"]


async def test_change_dates_reprices_and_respects_inventory(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory, rooms=1)
    a = await _book(client, prop, rt, plan, 10, 12)
    b = await _book(client, prop, rt, plan, 13, 15)
    url = f"/api/v1/reservations/{a['id']}/dates"

    # Extending A to the 13th collides with B on the only room.
    r = await _patch(client, url, {"check_in": d(10), "check_out": d(14)})
    assert r.status_code == 409
    assert r.json()["detail"] == f"Only 0 Tent rooms are free on {d(13)}."

    # Moving A within its own nights is not blocked by itself.
    r = await _patch(client, url, {"check_in": d(11), "check_out": d(13)})
    assert r.status_code == 200, r.text
    assert (r.json()["check_in"], r.json()["check_out"], r.json()["total_amount"]) == (
        d(11),
        d(13),
        "2000.00",
    )

    # Longer stay is re-priced at current rates.
    await client.put(
        f"/api/v1/rate-plans/{plan['id']}/prices/{rt['id']}",
        json={"base_price": "1200.00"},
        headers=await csrf(client),
    )
    r = await _patch(client, url, {"check_in": d(10), "check_out": d(13)})
    body = r.json()
    assert body["total_amount"] == "3600.00"
    assert [n["date"] for n in body["rooms"][0]["price_snapshot"]["nights"]] == [
        d(10),
        d(11),
        d(12),
    ]
    assert "total 2000.00 to 3600.00" in body["history"][-1]["reason"]
    assert b["status"] == "confirmed"


async def test_change_dates_keeps_assigned_room_or_refuses(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=2)
    a = await _book(client, prop, rt, plan, 20, 22, room_id=rooms[0]["id"])
    await _book(client, prop, rt, plan, 22, 24, room_id=rooms[0]["id"])
    r = await _patch(
        client, f"/api/v1/reservations/{a['id']}/dates", {"check_in": d(20), "check_out": d(23)}
    )
    assert r.status_code == 409
    assert (
        r.json()["detail"]
        == "An assigned room is taken on the new dates. Remove or change it first."
    )
    again = (await client.get(f"/api/v1/reservations/{a['id']}")).json()
    assert (again["check_out"], again["total_amount"]) == (d(22), "2000.00")  # unchanged


async def test_guest_details_can_be_corrected(client, factory) -> None:
    org, prop, rt, plan, _ = await _setup(client, factory)
    res = await _book(client, prop, rt, plan, 30, 31)
    gid = res["guest"]["id"]
    r = await _patch(
        client, f"/api/v1/guests/{gid}", {"phone": "+264 81 123 4567", "email": "NEW@Example.com"}
    )
    assert (r.json()["phone"], r.json()["email"]) == ("+264 81 123 4567", "new@example.com")
    assert (await _patch(client, f"/api/v1/guests/{gid}", {"first_name": ""})).status_code == 422
    log = (await client.get("/api/v1/organisation/audit-logs")).json()["items"][0]
    assert log["action"] == "guest.updated"
    assert log["data"] == {"fields": ["email", "phone"]}  # no personal data in the log

    await client.post("/api/v1/auth/logout", headers=await csrf(client))
    acc = await factory.user()
    await factory.member(org, acc, Role.ACCOUNTANT)
    await login(client, acc.email)
    assert (await _patch(client, f"/api/v1/guests/{gid}", {"notes": "x"})).status_code == 403
    assert (
        await _post(client, f"/api/v1/reservations/{res['id']}/check-in", {})
    ).status_code == 403


def test_today_is_a_date() -> None:
    assert isinstance(TODAY, date)
