"""Properties, buildings, room types and rooms."""

import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.main import app
from app.modules.organisations.models import Role
from tests.conftest import Factory, csrf, login

ROOM_TYPE = {
    "name": "Double Room",
    "code": "DBL",
    "base_occupancy": 2,
    "max_occupancy": 3,
    "max_adults": 3,
    "max_children": 1,
}


async def _as(client, factory: Factory, role: Role, org=None):
    org = org or await factory.organisation("Etosha Lodge")
    user = await factory.user()
    await factory.member(org, user, role)
    await login(client, user.email)
    return org, user


async def _post(client, url: str, body: dict):
    return await client.post(url, json=body, headers=await csrf(client))


async def _patch(client, url: str, body: dict):
    return await client.patch(url, json=body, headers=await csrf(client))


async def _property(client, name: str = "Etosha Lodge Main") -> dict:
    r = await _post(client, "/api/v1/properties", {"name": name, "property_type": "lodge"})
    assert r.status_code == 201, r.text
    return r.json()


async def _room_type(client, prop_id: str, **over) -> dict:
    r = await _post(client, f"/api/v1/properties/{prop_id}/room-types", ROOM_TYPE | over)
    assert r.status_code == 201, r.text
    return r.json()


# --- properties -------------------------------------------------------------------------


async def test_property_defaults_come_from_the_organisation(client, factory: Factory) -> None:
    await _as(client, factory, Role.OWNER)
    prop = await _property(client, "Etosha Lodge & Spa")
    assert prop["slug"] == "etosha-lodge-spa"
    assert prop["timezone"] == "Africa/Windhoek"
    assert prop["currency"] == "NAD"
    assert prop["country_code"] == "NA"
    assert prop["check_in_time"] == "14:00:00"
    assert prop["check_out_time"] == "10:00:00"

    r = await _post(
        client, "/api/v1/properties", {"name": "Etosha Lodge & Spa", "property_type": "lodge"}
    )
    assert r.status_code == 409


async def test_property_can_differ_from_organisation_and_be_updated(client, factory) -> None:
    await _as(client, factory, Role.OWNER)
    r = await _post(
        client,
        "/api/v1/properties",
        {
            "name": "Hwange Camp",
            "property_type": "safari_lodge",
            "timezone": "Africa/Harare",
            "currency": "USD",
            "country_code": "ZW",
            "check_in_time": "12:00",
            "check_out_time": "09:30",
        },
    )
    assert r.status_code == 201, r.text
    prop = r.json()
    assert (prop["timezone"], prop["currency"], prop["check_out_time"]) == (
        "Africa/Harare",
        "USD",
        "09:30:00",
    )
    r = await _patch(client, f"/api/v1/properties/{prop['id']}", {"check_in_time": "13:00"})
    assert r.json()["check_in_time"] == "13:00:00"
    for bad in ({"timezone": "Nowhere/Land"}, {"currency": "usd"}, {"slug": "x"}, {"name": None}):
        r = await _patch(client, f"/api/v1/properties/{prop['id']}", bad)
        assert r.status_code == 422, bad


async def test_archived_properties_are_hidden_by_default(client, factory) -> None:
    await _as(client, factory, Role.OWNER)
    prop = await _property(client)
    await _patch(client, f"/api/v1/properties/{prop['id']}", {"status": "archived"})
    assert (await client.get("/api/v1/properties")).json() == []
    listed = (await client.get("/api/v1/properties?include_archived=true")).json()
    assert [p["id"] for p in listed] == [prop["id"]]


async def test_receptionist_sees_properties_but_cannot_set_them_up(client, factory) -> None:
    org, _ = await _as(client, factory, Role.OWNER)
    prop = await _property(client)
    rt = await _room_type(client, prop["id"])
    await client.post("/api/v1/auth/logout", headers=await csrf(client))

    await _as(client, factory, Role.RECEPTIONIST, org)
    assert (await client.get("/api/v1/properties")).status_code == 200
    assert (await client.get(f"/api/v1/properties/{prop['id']}/rooms")).status_code == 200
    assert (
        await _post(client, "/api/v1/properties", {"name": "X Lodge", "property_type": "lodge"})
    ).status_code == 403
    assert (
        await _patch(client, f"/api/v1/properties/{prop['id']}", {"name": "Hacked"})
    ).status_code == 403
    assert (
        await _post(
            client, f"/api/v1/properties/{prop['id']}/room-types", ROOM_TYPE | {"code": "X"}
        )
    ).status_code == 403
    assert (
        await _patch(client, f"/api/v1/room-types/{rt['id']}", {"name": "Hacked"})
    ).status_code == 403


async def test_accountant_cannot_see_rooms(client, factory) -> None:
    org, _ = await _as(client, factory, Role.OWNER)
    prop = await _property(client)
    await client.post("/api/v1/auth/logout", headers=await csrf(client))
    await _as(client, factory, Role.ACCOUNTANT, org)
    assert (await client.get("/api/v1/properties")).status_code == 200
    assert (await client.get(f"/api/v1/properties/{prop['id']}/rooms")).status_code == 403


async def test_other_tenants_properties_are_not_found(client, factory) -> None:
    await _as(client, factory, Role.OWNER)
    theirs = await _property(client, "Their Lodge")
    await client.post("/api/v1/auth/logout", headers=await csrf(client))

    await _as(client, factory, Role.OWNER, await factory.organisation("Other Org"))
    pid = theirs["id"]
    assert (await client.get(f"/api/v1/properties/{pid}")).status_code == 404
    assert (await _patch(client, f"/api/v1/properties/{pid}", {"name": "Mine"})).status_code == 404
    assert (await client.get(f"/api/v1/properties/{pid}/rooms")).status_code == 404
    assert (
        await _post(client, f"/api/v1/properties/{pid}/room-types", ROOM_TYPE)
    ).status_code == 404
    assert (await client.get("/api/v1/properties")).json() == []


# --- buildings --------------------------------------------------------------------------


async def test_buildings(client, factory) -> None:
    await _as(client, factory, Role.MANAGER)
    prop = await _property(client)
    url = f"/api/v1/properties/{prop['id']}/buildings"
    b = (await _post(client, url, {"name": "Main House"})).json()
    assert (await _post(client, url, {"name": "Main House"})).status_code == 409
    r = await _patch(client, f"/api/v1/buildings/{b['id']}", {"status": "archived"})
    assert r.json()["status"] == "archived"


# --- room types -------------------------------------------------------------------------


async def test_room_type_validation(client, factory) -> None:
    await _as(client, factory, Role.OWNER)
    prop = await _property(client)
    url = f"/api/v1/properties/{prop['id']}/room-types"
    for bad in (
        {"max_occupancy": 1},  # below base occupancy
        {"max_adults": 4},  # above max occupancy
        {"code": "dbl"},  # lowercase
        {"base_occupancy": 0},
    ):
        assert (await _post(client, url, ROOM_TYPE | bad)).status_code == 422, bad
    rt = await _room_type(client, prop["id"])
    assert (await _post(client, url, ROOM_TYPE | {"name": "Other"})).status_code == 409  # code
    # A partial update is validated against the stored values.
    r = await _patch(client, f"/api/v1/room-types/{rt['id']}", {"max_occupancy": 1})
    assert r.status_code == 422


async def test_room_type_with_active_rooms_cannot_be_archived(client, factory) -> None:
    await _as(client, factory, Role.OWNER)
    prop = await _property(client)
    rt = await _room_type(client, prop["id"])
    await _post(
        client,
        f"/api/v1/properties/{prop['id']}/rooms/bulk",
        {"numbers": ["1", "2"], "room_type_id": rt["id"]},
    )
    r = await _patch(client, f"/api/v1/room-types/{rt['id']}", {"status": "archived"})
    assert r.status_code == 409
    assert "2 active room" in r.json()["detail"]
    types = (await client.get(f"/api/v1/properties/{prop['id']}/room-types")).json()
    assert types[0]["room_count"] == 2


# --- rooms ------------------------------------------------------------------------------


async def test_bulk_create_is_all_or_nothing(client, factory) -> None:
    await _as(client, factory, Role.OWNER)
    prop = await _property(client)
    rt = await _room_type(client, prop["id"])
    url = f"/api/v1/properties/{prop['id']}/rooms"

    r = await _post(
        client,
        f"{url}/bulk",
        {"numbers": ["101", "102", "103"], "room_type_id": rt["id"], "floor": "1"},
    )
    assert r.status_code == 201, r.text
    assert [room["number"] for room in r.json()] == ["101", "102", "103"]
    assert all(room["housekeeping_status"] == "dirty" for room in r.json())

    r = await _post(client, f"{url}/bulk", {"numbers": ["104", "102"], "room_type_id": rt["id"]})
    assert r.status_code == 409
    assert "102" in r.json()["detail"]
    r = await _post(client, f"{url}/bulk", {"numbers": ["105", "105"], "room_type_id": rt["id"]})
    assert r.status_code == 422
    numbers = [room["number"] for room in (await client.get(url)).json()]
    assert numbers == ["101", "102", "103"]  # neither failed request created anything


async def test_concurrent_creation_of_the_same_room_number(client, factory) -> None:
    """Two people adding room 7 at the same moment: exactly one succeeds."""
    await _as(client, factory, Role.OWNER)
    prop = await _property(client)
    rt = await _room_type(client, prop["id"])
    headers = await csrf(client)

    async def attempt() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", cookies=client.cookies
        ) as c:
            r = await c.post(
                f"/api/v1/properties/{prop['id']}/rooms",
                json={"number": "7", "room_type_id": rt["id"]},
                headers=headers,
            )
            return r.status_code

    results = sorted(await asyncio.gather(*(attempt() for _ in range(5))))
    assert results == [201, 409, 409, 409, 409]


async def test_room_must_use_type_and_building_of_its_own_property(client, factory) -> None:
    await _as(client, factory, Role.OWNER)
    a = await _property(client, "Property A")
    b = await _property(client, "Property B")
    rt_b = await _room_type(client, b["id"])
    building_b = (
        await _post(client, f"/api/v1/properties/{b['id']}/buildings", {"name": "B Wing"})
    ).json()
    rt_a = await _room_type(client, a["id"])

    url = f"/api/v1/properties/{a['id']}/rooms"
    assert (
        await _post(client, url, {"number": "1", "room_type_id": rt_b["id"]})
    ).status_code == 422
    assert (
        await _post(
            client,
            url,
            {"number": "1", "room_type_id": rt_a["id"], "building_id": building_b["id"]},
        )
    ).status_code == 422


async def test_database_rejects_cross_property_room_type(
    app_engine: AsyncEngine, client, factory
) -> None:
    """Even if application checks were bypassed, the composite foreign key holds."""
    org, _user = await _as(client, factory, Role.OWNER)
    a = await _property(client, "Property A")
    b = await _property(client, "Property B")
    rt_b = await _room_type(client, b["id"])
    async with app_engine.connect() as conn:
        tx = await conn.begin()
        await conn.execute(
            text("SELECT set_config('app.current_org_id', :o, true)"), {"o": str(org.id)}
        )
        with pytest.raises(DBAPIError, match="fk_rooms_room_type_same_property"):
            await conn.execute(
                text(
                    "INSERT INTO rooms (id, organisation_id, property_id, room_type_id, number,"
                    " status, housekeeping_status, maintenance_status)"
                    " VALUES (:id, :org, :prop, :rt, '9', 'active', 'dirty', 'none')"
                ),
                {"id": uuid.uuid4(), "org": org.id, "prop": a["id"], "rt": rt_b["id"]},
            )
        await tx.rollback()


async def test_runtime_role_cannot_delete_rooms(app_engine: AsyncEngine) -> None:
    async with app_engine.connect() as conn:
        tx = await conn.begin()
        with pytest.raises(DBAPIError, match="permission denied"):
            await conn.execute(text("DELETE FROM rooms"))
        await tx.rollback()


async def test_housekeeping_and_maintenance_are_separate(client, factory) -> None:
    org, _ = await _as(client, factory, Role.OWNER)
    prop = await _property(client)
    rt = await _room_type(client, prop["id"])
    room = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/rooms",
            {"number": "12", "room_type_id": rt["id"]},
        )
    ).json()
    await client.post("/api/v1/auth/logout", headers=await csrf(client))

    # Housekeeping can mark the room clean but cannot take it out of order.
    _, _hk_user = await _as(client, factory, Role.HOUSEKEEPING, org)
    r = await _post(
        client, f"/api/v1/rooms/{room['id']}/housekeeping", {"housekeeping_status": "clean"}
    )
    assert r.status_code == 200
    assert r.json()["housekeeping_status"] == "clean"
    assert r.json()["maintenance_status"] == "none"
    r = await _post(
        client,
        f"/api/v1/rooms/{room['id']}/maintenance",
        {"maintenance_status": "out_of_order", "reason": "Leak"},
    )
    assert r.status_code == 403
    assert (
        await _patch(client, f"/api/v1/rooms/{room['id']}", {"number": "13"})
    ).status_code == 403
    await client.post("/api/v1/auth/logout", headers=await csrf(client))

    # Maintenance takes it out of order; cleanliness is untouched.
    await _as(client, factory, Role.MAINTENANCE, org)
    url = f"/api/v1/rooms/{room['id']}/maintenance"
    assert (
        await _post(client, url, {"maintenance_status": "out_of_order"})
    ).status_code == 422  # no reason
    r = await _post(client, url, {"maintenance_status": "out_of_order", "reason": "Burst geyser"})
    assert r.json()["maintenance_status"] == "out_of_order"
    assert r.json()["maintenance_reason"] == "Burst geyser"
    assert r.json()["housekeeping_status"] == "clean"
    assert (
        await _post(
            client, f"/api/v1/rooms/{room['id']}/housekeeping", {"housekeeping_status": "dirty"}
        )
    ).status_code == 403
    r = await _post(client, url, {"maintenance_status": "none", "reason": "ignored"})
    assert r.json()["maintenance_reason"] is None


async def test_room_changes_are_audited(client, factory) -> None:
    await _as(client, factory, Role.OWNER)
    prop = await _property(client)
    rt = await _room_type(client, prop["id"])
    room = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/rooms",
            {"number": "3", "room_type_id": rt["id"]},
        )
    ).json()
    await _post(
        client, f"/api/v1/rooms/{room['id']}/housekeeping", {"housekeeping_status": "inspected"}
    )
    await _patch(client, f"/api/v1/rooms/{room['id']}", {"floor": "Ground"})
    actions = [
        i["action"] for i in (await client.get("/api/v1/organisation/audit-logs")).json()["items"]
    ]
    for expected in (
        "property.created",
        "room_type.created",
        "room.created",
        "room.housekeeping_changed",
        "room.updated",
    ):
        assert expected in actions
