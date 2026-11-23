"""The daily housekeeping list: what each room needs, and the steps staff record."""

import uuid
from datetime import timedelta

from app.modules.organisations.models import Role
from tests.conftest import login
from tests.test_reservations import _post, _setup
from tests.test_stays import TODAY, _book, d


async def _in_house(client, factory, prop, rt, plan, room, start: int, end: int):
    """A checked-in stay from ``start`` to ``end`` days from today (start may be past)."""
    res = await _book(client, prop, rt, plan, 0, max(end, 1), room_id=room["id"])
    r = await _post(client, f"/api/v1/reservations/{res['id']}/check-in", {})
    assert r.status_code == 200, r.text
    for table, key in (("reservations", "id"), ("reservation_rooms", "reservation_id")):
        await factory.execute(
            f"UPDATE {table} SET check_in = :a, check_out = :b WHERE {key} = :id",  # noqa: S608 (fixed table names)
            a=TODAY + timedelta(days=start),
            b=TODAY + timedelta(days=end),
            id=uuid.UUID(res["id"]),
        )
    return res


def _board_url(prop, day=None):
    url = f"/api/v1/properties/{prop['id']}/housekeeping"
    return f"{url}?date={day}" if day else url


async def _step(client, prop, room, body, day=None):
    return await _post(
        client,
        f"/api/v1/properties/{prop['id']}/housekeeping/{day or d(0)}/rooms/{room['id']}",
        body,
    )


def _room(board, number):
    return next(r for r in board["rooms"] if r["number"] == number)


async def _clean(client, room):
    r = await _post(
        client, f"/api/v1/rooms/{room['id']}/housekeeping", {"housekeeping_status": "clean"}
    )
    assert r.status_code == 200


async def test_board_says_what_each_room_needs(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=5)
    departing = await _in_house(client, factory, prop, rt, plan, rooms[0], -2, 0)
    await _in_house(client, factory, prop, rt, plan, rooms[1], -1, 2)
    await _clean(client, rooms[2])
    await _book(client, prop, rt, plan, 0, 2, room_id=rooms[3]["id"])  # dirty room, arrival
    await _clean(client, rooms[4])
    # Rooms 3 (clean, vacant) and 5 (clean, vacant): nothing to do. Room 4 arrives dirty.

    board = (await client.get(_board_url(prop))).json()
    assert board["date"] == d(0) == board["today"]
    r1, r2, r3, r4 = (_room(board, n) for n in "1234")
    assert (r1["kind"], r1["departing"], r1["guest_left"], r1["guests"]) == (
        "departure",
        True,
        False,
        2,
    )
    assert (r2["kind"], r2["staying"]) == ("stayover", True)
    assert r3["kind"] is None
    assert (r4["kind"], r4["arriving"]) == ("arrival", True)
    # Housekeeping never sees who the guests are.
    assert "guest_name" not in str(board) and "Nghifindaka" not in str(board)

    # The departure cannot be cleaned while the guest is still in the room.
    r = await _step(client, prop, rooms[0], {"action": "start"})
    assert r.status_code == 409
    assert r.json()["detail"] == "The guest in room 1 has not checked out yet."
    await _post(client, f"/api/v1/reservations/{departing['id']}/check-out", {})
    board = (await client.get(_board_url(prop))).json()
    assert _room(board, "1")["guest_left"] is True

    r = await _step(client, prop, rooms[0], {"action": "start"})
    assert r.status_code == 200, r.text
    assert _room(r.json(), "1")["task"]["status"] == "in_progress"
    r = await _step(client, prop, rooms[0], {"action": "done"})
    r1 = _room(r.json(), "1")
    assert (r1["task"]["status"], r1["housekeeping_status"]) == ("done", "clean")
    assert r1["task"]["completed_by_name"] and r1["task"]["assigned_to_name"]

    # Clean, vacant rooms need nothing.
    r = await _step(client, prop, rooms[2], {"action": "start"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Room 3 needs nothing today."


async def test_stayover_can_be_declined_with_a_reason_only(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=2)
    await _in_house(client, factory, prop, rt, plan, rooms[0], -1, 2)
    r = await _step(client, prop, rooms[0], {"action": "decline"})
    assert r.status_code == 422
    r = await _step(client, prop, rooms[0], {"action": "decline", "note": "Do not disturb"})
    assert r.status_code == 200
    task = _room(r.json(), "1")["task"]
    assert (task["status"], task["note"]) == ("declined", "Do not disturb")
    # A vacant dirty room cannot be "declined".
    r = await _step(client, prop, rooms[1], {"action": "decline", "note": "No"})
    assert r.status_code == 409


async def test_reopen_sends_room_back_to_dirty(client, factory) -> None:
    _, prop, _, _, rooms = await _setup(client, factory, rooms=1)
    assert _room((await client.get(_board_url(prop))).json(), "1")["kind"] == "vacant"
    await _step(client, prop, rooms[0], {"action": "done"})
    r = await _step(client, prop, rooms[0], {"action": "done"})
    assert r.status_code == 409
    r = await _step(client, prop, rooms[0], {"action": "reopen", "note": "Bathroom missed"})
    r1 = _room(r.json(), "1")
    assert (r1["kind"], r1["task"]["status"], r1["housekeeping_status"]) == (
        "vacant",
        "pending",
        "dirty",
    )
    assert r1["task"]["note"] == "Bathroom missed"


async def test_assignment_and_dates(client, factory) -> None:
    org, prop, rt, plan, rooms = await _setup(client, factory, rooms=2)
    keeper = await factory.user()
    await factory.member(org, keeper, Role.HOUSEKEEPING, property_id=prop["id"])
    fixer = await factory.user()
    await factory.member(org, fixer, Role.MAINTENANCE)
    board = (await client.get(_board_url(prop))).json()
    names = [a["name"] for a in board["assignees"]]
    assert keeper.full_name in names and fixer.full_name not in names

    # Tomorrow's departures can be planned and assigned, not worked.
    await _book(client, prop, rt, plan, 0, 1, room_id=rooms[0]["id"])
    tomorrow = (await client.get(_board_url(prop, d(1)))).json()
    assert _room(tomorrow, "1")["kind"] == "departure"
    r = await _step(
        client, prop, rooms[0], {"action": "assign", "assigned_to": str(keeper.id)}, d(1)
    )
    assert r.status_code == 200
    assert _room(r.json(), "1")["task"]["assigned_to_name"] == keeper.full_name
    r = await _step(client, prop, rooms[0], {"action": "done"}, d(1))
    assert r.status_code == 409
    assert r.json()["detail"] == "Rooms can only be worked on today."
    r = await _step(client, prop, rooms[0], {"action": "assign", "assigned_to": None}, d(-1))
    assert r.status_code == 409

    # Only people who do housekeeping here can be assigned.
    r = await _step(client, prop, rooms[1], {"action": "assign", "assigned_to": str(fixer.id)})
    assert r.status_code == 422


async def test_permissions_and_isolation(client, factory) -> None:
    org, prop, _, _, rooms = await _setup(client, factory, rooms=1)
    fixer = await factory.user()
    await factory.member(org, fixer, Role.MAINTENANCE)
    keeper = await factory.user()
    await factory.member(org, keeper, Role.HOUSEKEEPING)

    await login(client, fixer.email)
    assert (await client.get(_board_url(prop))).status_code == 200  # can see rooms
    assert (await _step(client, prop, rooms[0], {"action": "done"})).status_code == 403

    await login(client, keeper.email)
    r = await _step(client, prop, rooms[0], {"action": "done"})
    assert r.status_code == 200
    assert _room(r.json(), "1")["task"]["completed_by_name"] == keeper.full_name

    # Another organisation sees neither the property nor its rooms.
    other = await factory.organisation("Elsewhere")
    stranger = await factory.user()
    await factory.member(other, stranger, Role.OWNER)
    await login(client, stranger.email)
    assert (await client.get(_board_url(prop))).status_code == 404
    assert (await _step(client, prop, rooms[0], {"action": "reopen"})).status_code == 404


async def test_early_departure_is_cleaned_the_day_the_guest_leaves(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=1)
    res = await _book(client, prop, rt, plan, 0, 3, room_id=rooms[0]["id"])
    await _post(client, f"/api/v1/reservations/{res['id']}/check-in", {})
    # Arrival day, guest just checked in: nothing to do yet.
    assert _room((await client.get(_board_url(prop))).json(), "1")["kind"] is None
    await _post(client, f"/api/v1/reservations/{res['id']}/check-out", {})
    r1 = _room((await client.get(_board_url(prop))).json(), "1")
    assert (r1["kind"], r1["departing"], r1["guest_left"]) == ("departure", True, True)
    # Not a departure again on the booked departure day, nor a stay-over in between.
    later = (await client.get(_board_url(prop, d(1)))).json()
    assert _room(later, "1")["kind"] == "vacant"
    assert _room((await client.get(_board_url(prop, d(3)))).json(), "1")["departing"] is False
