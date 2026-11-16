"""Staff invitations: create, preview, accept, expire, revoke."""

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.security import hash_token
from app.main import app
from app.modules.organisations.models import Role
from tests.conftest import PASSWORD, Factory, csrf, login

NEW_PASSWORD = "a strong new password"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def _owner_with_property(client, factory: Factory):
    org = await factory.organisation("Sesriem Lodge")
    owner = await factory.user()
    await factory.member(org, owner, Role.OWNER)
    await login(client, owner.email)
    prop = (
        await client.post(
            "/api/v1/properties",
            json={"name": "Sesriem Main", "property_type": "lodge"},
            headers=await csrf(client),
        )
    ).json()
    roles = {r["key"]: r["id"] for r in (await client.get("/api/v1/roles")).json()}
    return org, owner, prop, roles


async def _invite(client, **body):
    return await client.post("/api/v1/invitations", json=body, headers=await csrf(client))


async def _accept(c: httpx.AsyncClient, token: str, password: str, **extra):
    return await c.post(
        "/api/v1/invitations/accept",
        json={"token": token, "password": password, **extra},
        headers=await csrf(c),
    )


async def test_invite_and_accept_as_a_new_person(
    client, factory, owner_engine: AsyncEngine
) -> None:
    _, _, prop, roles = await _owner_with_property(client, factory)
    r = await _invite(
        client,
        email="  Selma@Example.com ",
        full_name="Selma Shikongo",
        role_id=roles["receptionist"],
        property_id=prop["id"],
    )
    assert r.status_code == 201, r.text
    created = r.json()
    token = created["token"]
    assert created["email"] == "selma@example.com"
    assert created["state"] == "pending"

    # Only the hash is stored.
    async with owner_engine.connect() as conn:
        stored = (await conn.execute(text("SELECT token_hash FROM invitations"))).scalar_one()
    assert stored == hash_token(token)

    pending = (await client.get("/api/v1/invitations")).json()
    assert [i["email"] for i in pending] == ["selma@example.com"]
    assert "token" not in pending[0]

    async with _client() as guest:
        preview = (await guest.get(f"/api/v1/invitations/token/{token}")).json()
        assert preview == {
            "organisation_name": "Sesriem Lodge",
            "email": "selma@example.com",
            "full_name": "Selma Shikongo",
            "role_name": "Receptionist",
            "property_name": "Sesriem Main",
            "has_account": False,
        }
        assert (await _accept(guest, token, "short")).status_code == 422
        r = await _accept(guest, token, NEW_PASSWORD)
        assert r.status_code == 200, r.text
        me = r.json()
        assert me["user"]["full_name"] == "Selma Shikongo"
        assert me["active_organisation"]["role_label"] == "Receptionist (1 property)"
        # Signed in straight away.
        assert (await guest.get("/api/v1/properties")).json()[0]["name"] == "Sesriem Main"

        # The link works once.
        assert (await _accept(guest, token, NEW_PASSWORD)).status_code == 410

    assert (await client.get("/api/v1/invitations")).json() == []
    actions = [
        i["action"] for i in (await client.get("/api/v1/organisation/audit-logs")).json()["items"]
    ]
    assert {"invitation.created", "invitation.accepted"} <= set(actions)


async def test_existing_account_must_prove_ownership(client, factory) -> None:
    other_org = await factory.organisation("Elsewhere")
    existing = await factory.user("tuli@example.com")
    await factory.member(other_org, existing, Role.MANAGER)

    _, _, _, roles = await _owner_with_property(client, factory)
    token = (
        await _invite(
            client, email="tuli@example.com", full_name="Tuli", role_id=roles["accountant"]
        )
    ).json()["token"]

    async with _client() as guest:
        assert (await guest.get(f"/api/v1/invitations/token/{token}")).json()["has_account"] is True
        # Knowing the link is not enough to attach an existing account.
        assert (await _accept(guest, token, "not their password")).status_code == 401
        r = await _accept(guest, token, PASSWORD)
        assert r.status_code == 200
        orgs = {m["organisation_name"]: m["role_label"] for m in r.json()["memberships"]}
        assert orgs == {"Elsewhere": "Manager", "Sesriem Lodge": "Accountant"}
        assert r.json()["active_organisation"]["name"] == "Sesriem Lodge"


async def test_reinvite_replaces_old_link_and_revoke_and_expiry(client, factory) -> None:
    _, _, _, roles = await _owner_with_property(client, factory)
    body = {
        "email": "ndapewa@example.com",
        "full_name": "Ndapewa",
        "role_id": roles["housekeeping"],
    }
    first = (await _invite(client, **body)).json()
    second = (await _invite(client, **body)).json()
    async with _client() as guest:
        assert (await guest.get(f"/api/v1/invitations/token/{first['token']}")).status_code == 410
        assert (await guest.get(f"/api/v1/invitations/token/{second['token']}")).status_code == 200

    r = await client.post(f"/api/v1/invitations/{second['id']}/revoke", headers=await csrf(client))
    assert r.json()["state"] == "revoked"
    async with _client() as guest:
        r = await guest.get(f"/api/v1/invitations/token/{second['token']}")
        assert r.status_code == 410
        assert "withdrawn" in r.json()["detail"]

    third = (await _invite(client, **body)).json()
    await factory.execute("UPDATE invitations SET expires_at = now() - interval '1 minute'")
    async with _client() as guest:
        r = await guest.get(f"/api/v1/invitations/token/{third['token']}")
        assert r.status_code == 410
        assert "expired" in r.json()["detail"]
        assert (await guest.get("/api/v1/invitations/token/" + "x" * 43)).status_code == 404


async def test_invitation_rules(client, factory) -> None:
    org, owner, prop, roles = await _owner_with_property(client, factory)
    assert (
        await _invite(client, email=owner.email, full_name="Me", role_id=roles["manager"])
    ).status_code == 409  # already on the team
    assert (
        await _invite(
            client,
            email="x@example.com",
            full_name="X",
            role_id=roles["owner"],
            property_id=prop["id"],
        )
    ).status_code == 422
    assert (
        await _invite(client, email="not-an-email", full_name="X", role_id=roles["manager"])
    ).status_code == 422

    mgr = await factory.user()
    await factory.member(org, mgr, Role.MANAGER)
    async with _client() as c:
        await login(c, mgr.email)
        r = await _invite(c, email="boss@example.com", full_name="Boss", role_id=roles["owner"])
        assert r.status_code == 403
        r = await _invite(
            c, email="desk@example.com", full_name="Desk", role_id=roles["receptionist"]
        )
        assert r.status_code == 201

    desk = await factory.user()
    await factory.member(org, desk, Role.RECEPTIONIST)
    async with _client() as c:
        await login(c, desk.email)
        assert (await c.get("/api/v1/invitations")).status_code == 403
        r = await _invite(c, email="y@example.com", full_name="Y", role_id=roles["housekeeping"])
        assert r.status_code == 403


async def test_token_lookup_is_rate_limited(factory) -> None:
    async with _client() as guest:
        codes = [
            (await guest.get("/api/v1/invitations/token/" + "y" * 43)).status_code
            for _ in range(31)
        ]
    assert codes[:30] == [404] * 30
    assert codes[30] == 429
