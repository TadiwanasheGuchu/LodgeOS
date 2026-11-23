"""Maintenance tickets and dated room blocks, and how blocks interact with bookings."""

from app.modules.organisations.models import Role
from tests.conftest import csrf, login
from tests.test_reservations import _booking, _post, _setup


async def _patch(client, url, body):
    return await client.patch(url, json=body, headers=await csrf(client))


async def _ticket(client, prop, room, title="Geyser leaking"):
    r = await _post(
        client,
        f"/api/v1/properties/{prop['id']}/maintenance/tickets",
        {"room_id": room["id"], "title": title, "priority": "urgent"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_block_removes_room_from_sale_only_on_its_nights(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=1)
    t = await _ticket(client, prop, rooms[0])
    r = await _post(
        client,
        f"/api/v1/maintenance/tickets/{t['id']}/blocks",
        {"start_date": "2027-02-03", "end_date": "2027-02-06"},
    )
    assert r.status_code == 201, r.text
    url = f"/api/v1/properties/{prop['id']}/reservations"
    r = await _post(client, url, _booking(rt, plan, "2027-02-05", "2027-02-07"))
    assert r.status_code == 409
    assert r.json()["detail"] == "Only 0 Tent rooms are free on 2027-02-05."
    # The night the room comes back is sellable; the night before the block too.
    assert (
        await _post(client, url, _booking(rt, plan, "2027-02-06", "2027-02-07"))
    ).status_code == 201
    assert (
        await _post(client, url, _booking(rt, plan, "2027-02-02", "2027-02-03"))
    ).status_code == 201
    avail = (
        await client.get(
            f"/api/v1/properties/{prop['id']}/availability",
            params={"check_in": "2027-02-02", "check_out": "2027-02-07"},
        )
    ).json()
    assert [n["sellable"] for n in avail[0]["nights"]] == [1, 0, 0, 0, 1]


async def test_block_refused_when_guests_are_in_the_room_or_type_would_be_oversold(
    client, factory
) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=2)
    url = f"/api/v1/properties/{prop['id']}/reservations"
    guest = (
        await _post(
            client, url, _booking(rt, plan, "2027-03-01", "2027-03-03", room_id=rooms[0]["id"])
        )
    ).json()
    t = await _ticket(client, prop, rooms[0])
    r = await _post(
        client,
        f"/api/v1/maintenance/tickets/{t['id']}/blocks",
        {"start_date": "2027-03-02", "end_date": "2027-03-04"},
    )
    assert r.status_code == 409
    assert guest["reference"] in r.json()["detail"]

    # Two bookings without rooms fill both tents on 10 March: blocking either would oversell.
    await _post(client, url, _booking(rt, plan, "2027-03-10", "2027-03-11"))
    await _post(client, url, _booking(rt, plan, "2027-03-10", "2027-03-11"))
    t2 = await _ticket(client, prop, rooms[1], "Broken window")
    r = await _post(
        client,
        f"/api/v1/maintenance/tickets/{t2['id']}/blocks",
        {"start_date": "2027-03-09", "end_date": "2027-03-12"},
    )
    assert r.status_code == 409
    assert (
        r.json()["detail"]
        == "Blocking room 2 would oversell Tent on 2027-03-10. Move or cancel a booking first."
    )


async def test_blocked_room_is_not_offered_or_assignable(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=2)
    t = await _ticket(client, prop, rooms[0])
    await _post(
        client,
        f"/api/v1/maintenance/tickets/{t['id']}/blocks",
        {"start_date": "2027-04-01", "end_date": "2027-04-03"},
    )
    res = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/reservations",
            _booking(rt, plan, "2027-04-02", "2027-04-04"),
        )
    ).json()
    rr = res["rooms"][0]["id"]
    assert [
        r["number"] for r in (await client.get(f"/api/v1/reservation-rooms/{rr}/free-rooms")).json()
    ] == ["2"]
    r = await _post(client, f"/api/v1/reservation-rooms/{rr}/assign", {"room_id": rooms[0]["id"]})
    assert r.status_code == 409
    assert "blocked for maintenance" in r.json()["detail"]
    assert (
        await _post(
            client,
            f"/api/v1/maintenance/tickets/{t['id']}/blocks",
            {"start_date": "2027-04-02", "end_date": "2027-04-05"},
        )
    ).status_code == 409


async def test_resolving_releases_blocks(client, factory) -> None:
    _, prop, rt, plan, rooms = await _setup(client, factory, rooms=1)
    t = await _ticket(client, prop, rooms[0])
    await _post(
        client,
        f"/api/v1/maintenance/tickets/{t['id']}/blocks",
        {"start_date": "2027-05-01", "end_date": "2027-05-10"},
    )
    url = f"/api/v1/maintenance/tickets/{t['id']}"
    assert (await _patch(client, url, {"status": "resolved"})).status_code == 422  # needs a note
    r = await _patch(
        client, url, {"status": "resolved", "resolution": "Replaced the geyser element"}
    )
    body = r.json()
    assert body["status"] == "resolved" and body["closed_at"]
    assert [b["status"] for b in body["blocks"]] == ["released"]
    assert (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/reservations",
            _booking(rt, plan, "2027-05-03", "2027-05-05"),
        )
    ).status_code == 201
    assert (await _patch(client, url, {"priority": "low"})).status_code == 409  # closed


async def test_tickets_list_and_assignment(client, factory) -> None:
    org, prop, _, _, rooms = await _setup(client, factory)
    await _post(
        client,
        f"/api/v1/properties/{prop['id']}/maintenance/tickets",
        {"location": "Swimming pool", "title": "Pump noisy", "priority": "low"},
    )
    urgent = await _ticket(client, prop, rooms[0])
    listed = (await client.get(f"/api/v1/properties/{prop['id']}/maintenance/tickets")).json()
    assert [t["title"] for t in listed] == ["Geyser leaking", "Pump noisy"]  # urgent first
    assert listed[1]["room_number"] is None and listed[1]["location"] == "Swimming pool"
    assert (
        await _post(
            client, f"/api/v1/properties/{prop['id']}/maintenance/tickets", {"title": "Somewhere"}
        )
    ).status_code == 422

    fixer = await factory.user()
    await factory.member(org, fixer, Role.MAINTENANCE)
    r = await _patch(
        client,
        f"/api/v1/maintenance/tickets/{urgent['id']}",
        {"assigned_to": str(fixer.id), "status": "in_progress"},
    )
    assert r.json()["assigned_to_name"] == fixer.full_name
    outsider = await factory.user()
    assert (
        await _patch(
            client, f"/api/v1/maintenance/tickets/{urgent['id']}", {"assigned_to": str(outsider.id)}
        )
    ).status_code == 422


async def test_housekeeping_reports_but_cannot_block(client, factory) -> None:
    org, prop, _, _, rooms = await _setup(client, factory)
    await client.post("/api/v1/auth/logout", headers=await csrf(client))
    hk = await factory.user()
    await factory.member(org, hk, Role.HOUSEKEEPING)
    await login(client, hk.email)
    t = await _ticket(client, prop, rooms[0], "Shower drain blocked")
    assert t["reported_by_name"] == hk.full_name
    assert (
        await _post(
            client,
            f"/api/v1/maintenance/tickets/{t['id']}/blocks",
            {"start_date": "2027-06-01", "end_date": "2027-06-02"},
        )
    ).status_code == 403
    assert (
        await _patch(client, f"/api/v1/maintenance/tickets/{t['id']}", {"status": "in_progress"})
    ).status_code == 403
