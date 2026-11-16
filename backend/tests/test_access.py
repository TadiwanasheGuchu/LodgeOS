"""Database-backed roles, property-scoped access and staff management."""

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.main import app
from app.modules.auth.permissions import ROLE_PERMISSIONS, Permission
from app.modules.organisations.models import Role
from tests.conftest import Factory, csrf, login


async def _post(client, url, body):
    return await client.post(url, json=body, headers=await csrf(client))


async def _logout(client):
    await client.post("/api/v1/auth/logout", headers=await csrf(client))


async def _setup(client, factory: Factory):
    """An organisation with two properties, each with one room, created by the owner."""
    org = await factory.organisation("Kunene Group")
    owner = await factory.user("owner@kunene.example.com")
    owner_m = await factory.member(org, owner, Role.OWNER)
    await login(client, owner.email)
    props, rooms = [], []
    for name in ("Lodge A", "Lodge B"):
        p = (
            await _post(client, "/api/v1/properties", {"name": name, "property_type": "lodge"})
        ).json()
        rt = (
            await _post(
                client,
                f"/api/v1/properties/{p['id']}/room-types",
                {
                    "name": "Twin",
                    "code": "TWN",
                    "base_occupancy": 2,
                    "max_occupancy": 2,
                    "max_adults": 2,
                },
            )
        ).json()
        room = (
            await _post(
                client,
                f"/api/v1/properties/{p['id']}/rooms",
                {"number": "1", "room_type_id": rt["id"]},
            )
        ).json()
        props.append(p)
        rooms.append(room)
    await _logout(client)
    return org, owner, owner_m, props, rooms


async def test_catalogue_and_system_roles_match_the_code(
    owner_engine: AsyncEngine, factory
) -> None:
    org = await factory.organisation()
    async with owner_engine.connect() as conn:
        codes = set((await conn.execute(text("SELECT code FROM permissions"))).scalars())
        assert codes == {p.value for p in Permission}, "add a migration for permission changes"
        rows = await conn.execute(
            text(
                "SELECT r.key, p.code FROM roles r JOIN role_permissions rp ON rp.role_id = r.id"
                " JOIN permissions p ON p.id = rp.permission_id WHERE r.organisation_id = :o"
            ),
            {"o": org.id},
        )
        db_roles: dict[str, set[str]] = {}
        for key, code in rows:
            db_roles.setdefault(key, set()).add(code)
    assert db_roles == {r.value: {p.value for p in ps} for r, ps in ROLE_PERMISSIONS.items()}


async def test_property_scoped_receptionist_sees_only_their_property(client, factory) -> None:
    org, _, _, (a, b), (room_a, room_b) = await _setup(client, factory)
    desk = await factory.user("desk@kunene.example.com")
    await factory.member(org, desk, Role.RECEPTIONIST, property_id=a["id"])
    me = (await login(client, desk.email)).json()

    active = me["active_organisation"]
    assert active["permissions"] == ["organisation.view"]  # nothing property-related everywhere
    assert set(active["property_permissions"]) == {a["id"]}
    assert "rooms.housekeeping_update" in active["property_permissions"][a["id"]]
    assert active["role_label"] == "Receptionist (1 property)"

    listed = (await client.get("/api/v1/properties")).json()
    assert [p["name"] for p in listed] == ["Lodge A"]
    assert (await client.get(f"/api/v1/properties/{b['id']}")).status_code == 404
    assert (await client.get(f"/api/v1/properties/{b['id']}/rooms")).status_code == 404
    assert (await client.get(f"/api/v1/properties/{a['id']}/rooms")).status_code == 200

    url = "/api/v1/rooms/{}/housekeeping"
    assert (
        await _post(client, url.format(room_a["id"]), {"housekeeping_status": "clean"})
    ).status_code == 200
    assert (
        await _post(client, url.format(room_b["id"]), {"housekeeping_status": "clean"})
    ).status_code == 404
    # A role for one property never allows creating properties.
    assert (
        await _post(client, "/api/v1/properties", {"name": "C", "property_type": "lodge"})
    ).status_code == 403


async def test_property_scoped_manager_cannot_change_other_property(client, factory) -> None:
    org, _, _, (a, b), _ = await _setup(client, factory)
    mgr = await factory.user()
    await factory.member(org, mgr, Role.MANAGER, property_id=a["id"])
    await login(client, mgr.email)
    patch = lambda pid: client.patch(  # noqa: E731
        f"/api/v1/properties/{pid}", json={"check_in_time": "12:00"}, headers=client_headers
    )
    client_headers = await csrf(client)
    assert (await patch(a["id"])).status_code == 200
    assert (await patch(b["id"])).status_code == 404
    # members.manage was granted for one property only, which does not allow staff changes.
    assert (await client.get("/api/v1/organisation/members")).status_code == 403


async def test_manager_cannot_create_or_remove_owners(client, factory) -> None:
    org, owner, owner_m, _, _ = await _setup(client, factory)
    mgr = await factory.user()
    await factory.member(org, mgr, Role.MANAGER)
    staff = await factory.user()
    staff_m = await factory.member(org, staff, Role.HOUSEKEEPING)
    await login(client, mgr.email)

    roles = {r["key"]: r for r in (await client.get("/api/v1/roles")).json()}
    assert list(roles) == [r.value for r in Role]

    r = await _post(
        client, f"/api/v1/members/{staff_m.id}/roles", {"role_id": roles["owner"]["id"]}
    )
    assert r.status_code == 403
    r = await _post(
        client, f"/api/v1/members/{staff_m.id}/roles", {"role_id": roles["receptionist"]["id"]}
    )
    assert r.status_code == 201
    assert {a["role_name"] for a in r.json()["assignments"]} == {"Housekeeping", "Receptionist"}

    members = {m["email"]: m for m in (await client.get("/api/v1/organisation/members")).json()}
    owner_assignment = members[owner.email]["assignments"][0]["id"]
    r = await client.delete(
        f"/api/v1/members/{owner_m.id}/roles/{owner_assignment}", headers=await csrf(client)
    )
    assert r.status_code == 403
    r = await client.patch(
        f"/api/v1/members/{owner_m.id}", json={"status": "disabled"}, headers=await csrf(client)
    )
    assert r.status_code == 403


async def test_last_owner_is_protected(client, factory) -> None:
    org, owner, owner_m, (a, _), _ = await _setup(client, factory)
    await login(client, owner.email)
    roles = {r["key"]: r["id"] for r in (await client.get("/api/v1/roles")).json()}
    members = {m["email"]: m for m in (await client.get("/api/v1/organisation/members")).json()}
    own = members[owner.email]["assignments"][0]["id"]

    r = await client.delete(f"/api/v1/members/{owner_m.id}/roles/{own}", headers=await csrf(client))
    assert r.status_code == 409
    r = await client.patch(
        f"/api/v1/members/{owner_m.id}", json={"status": "disabled"}, headers=await csrf(client)
    )
    assert r.status_code == 422  # not even for yourself

    # With a second owner, one can step down.
    other = await factory.user()
    other_m = await factory.member(org, other, Role.HOUSEKEEPING)
    assert (
        await _post(client, f"/api/v1/members/{other_m.id}/roles", {"role_id": roles["owner"]})
    ).status_code == 201
    # Owner role cannot be limited to one property.
    r = await _post(
        client,
        f"/api/v1/members/{other_m.id}/roles",
        {"role_id": roles["owner"], "property_id": a["id"]},
    )
    assert r.status_code == 422
    # The same grant twice is refused.
    assert (
        await _post(client, f"/api/v1/members/{other_m.id}/roles", {"role_id": roles["owner"]})
    ).status_code == 409
    r = await client.delete(f"/api/v1/members/{owner_m.id}/roles/{own}", headers=await csrf(client))
    assert r.status_code == 200


async def test_removing_a_role_takes_effect_immediately(client, factory) -> None:
    org, owner, _, (a, _), _ = await _setup(client, factory)
    staff = await factory.user()
    staff_m = await factory.member(org, staff, Role.MAINTENANCE)
    await login(client, staff.email)
    assert (await client.get(f"/api/v1/properties/{a['id']}/rooms")).status_code == 200

    # The owner works in a separate browser while the staff member stays signed in.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as owner_client:
        await login(owner_client, owner.email)
        members = (await owner_client.get("/api/v1/organisation/members")).json()
        assignment = next(m for m in members if m["email"] == staff.email)["assignments"][0]["id"]
        r = await owner_client.delete(
            f"/api/v1/members/{staff_m.id}/roles/{assignment}", headers=await csrf(owner_client)
        )
        assert r.status_code == 200
        assert r.json()["role_label"] == "No access"

    assert (await client.get(f"/api/v1/properties/{a['id']}/rooms")).status_code == 403


async def test_picker_shows_roles_in_other_organisations(client, factory) -> None:
    """RLS lets a user read their own role assignments in every organisation, and only those."""
    a = await factory.organisation("Alpha")
    b = await factory.organisation("Bravo")
    user = await factory.user()
    await factory.member(a, user, Role.OWNER)
    await factory.member(b, user, Role.ACCOUNTANT)
    other = await factory.user()
    await factory.member(b, other, Role.MANAGER)

    me = (await login(client, user.email)).json()
    labels = {m["organisation_name"]: m["role_label"] for m in me["memberships"]}
    assert labels == {"Alpha": "Owner", "Bravo": "Accountant"}


async def test_role_changes_are_audited(client, factory) -> None:
    org, owner, _, _, _ = await _setup(client, factory)
    staff = await factory.user()
    staff_m = await factory.member(org, staff, Role.HOUSEKEEPING)
    await login(client, owner.email)
    roles = {r["key"]: r["id"] for r in (await client.get("/api/v1/roles")).json()}
    await _post(client, f"/api/v1/members/{staff_m.id}/roles", {"role_id": roles["maintenance"]})
    await client.patch(
        f"/api/v1/members/{staff_m.id}", json={"status": "disabled"}, headers=await csrf(client)
    )
    actions = [
        i["action"] for i in (await client.get("/api/v1/organisation/audit-logs")).json()["items"]
    ]
    assert "member.role_added" in actions and "member.disabled" in actions


async def test_roles_from_other_organisations_are_never_listed_or_usable(client, factory) -> None:
    """Regression: the own-assignments RLS policy made a user's roles in another
    organisation visible; they must not appear in, or be accepted by, this one."""
    home = await factory.organisation("Home")
    elsewhere = await factory.organisation("Elsewhere")
    mgr = await factory.user()
    await factory.member(home, mgr, Role.MANAGER)
    await factory.member(elsewhere, mgr, Role.OWNER)
    staff = await factory.user()
    staff_m = await factory.member(home, staff, Role.HOUSEKEEPING)

    me = (await login(client, mgr.email)).json()
    home_id = next(
        m["organisation_id"] for m in me["memberships"] if m["organisation_name"] == "Home"
    )
    await _post(client, "/api/v1/auth/active-organisation", {"organisation_id": home_id})

    roles = (await client.get("/api/v1/roles")).json()
    assert [r["name"] for r in roles] == [
        "Owner",
        "Manager",
        "Receptionist",
        "Housekeeping",
        "Maintenance",
        "Accountant",
    ]
    assert all(r["permissions"] for r in roles)

    async with factory.engine.connect() as conn:
        foreign_owner = (
            await conn.execute(
                text("SELECT id FROM roles WHERE organisation_id = :o AND key = 'owner'"),
                {"o": elsewhere.id},
            )
        ).scalar_one()
    r = await _post(client, f"/api/v1/members/{staff_m.id}/roles", {"role_id": str(foreign_owner)})
    assert r.status_code == 422
    r = await _post(
        client,
        "/api/v1/invitations",
        {"email": "z@example.com", "full_name": "Z", "role_id": str(foreign_owner)},
    )
    assert r.status_code == 422


async def test_own_rows_in_other_organisations_are_not_found(client, factory) -> None:
    """A user's membership and role assignment in another organisation are readable under
    RLS, but endpoints acting on the active organisation must treat them as not found."""
    home = await factory.organisation("Home")
    elsewhere = await factory.organisation("Elsewhere")
    mgr = await factory.user()
    await factory.member(home, mgr, Role.OWNER)
    other_m = await factory.member(elsewhere, mgr, Role.HOUSEKEEPING)
    me = (await login(client, mgr.email)).json()
    home_id = next(
        m["organisation_id"] for m in me["memberships"] if m["organisation_name"] == "Home"
    )
    await _post(client, "/api/v1/auth/active-organisation", {"organisation_id": home_id})
    async with factory.engine.connect() as conn:
        other_assignment = (
            await conn.execute(
                text("SELECT id FROM user_roles WHERE membership_id = :m"), {"m": other_m.id}
            )
        ).scalar_one()

    headers = await csrf(client)
    r = await client.patch(
        f"/api/v1/members/{other_m.id}", json={"status": "disabled"}, headers=headers
    )
    assert r.status_code == 404
    r = await client.delete(
        f"/api/v1/members/{other_m.id}/roles/{other_assignment}", headers=headers
    )
    assert r.status_code == 404
    roles = {r["key"]: r["id"] for r in (await client.get("/api/v1/roles")).json()}
    r = await _post(client, f"/api/v1/members/{other_m.id}/roles", {"role_id": roles["manager"]})
    assert r.status_code == 404
