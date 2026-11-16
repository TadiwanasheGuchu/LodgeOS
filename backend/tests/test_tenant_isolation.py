"""Tenant isolation, tested at both layers: through the API, and directly against
PostgreSQL as the runtime role to prove RLS holds even if application code is wrong."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.modules.organisations.models import Role
from tests.conftest import Factory, csrf, login


async def _two_tenants(factory: Factory):
    a = await factory.organisation("Alpha Lodge")
    b = await factory.organisation("Bravo Guesthouse")
    ua = await factory.user("alpha@example.com")
    ub = await factory.user("bravo@example.com")
    await factory.member(a, ua, Role.OWNER)
    await factory.member(b, ub, Role.OWNER)
    return a, b, ua, ub


async def _as_tenant(conn: AsyncConnection, user_id: uuid.UUID | None, org_id: uuid.UUID | None):
    await conn.execute(
        text(
            "SELECT set_config('app.current_user_id', :u, true),"
            " set_config('app.current_org_id', :o, true)"
        ),
        {"u": str(user_id) if user_id else "", "o": str(org_id) if org_id else ""},
    )


# --- through the API --------------------------------------------------------------------


async def test_api_only_returns_the_callers_organisation(client, factory: Factory) -> None:
    a, _b, ua, _ = await _two_tenants(factory)
    await login(client, ua.email)

    org = (await client.get("/api/v1/organisation")).json()
    assert org["id"] == str(a.id)

    members = (await client.get("/api/v1/organisation/members")).json()
    assert [m["email"] for m in members] == ["alpha@example.com"]

    logs = (await client.get("/api/v1/organisation/audit-logs")).json()["items"]
    assert logs and all(log["action"].startswith("auth.") for log in logs)


async def test_organisation_id_in_request_body_is_ignored(client, factory: Factory) -> None:
    _a, b, ua, _ = await _two_tenants(factory)
    await login(client, ua.email)
    # An attacker adds another tenant's id to the payload. The schema forbids unknown
    # fields, and the organisation always comes from the session.
    r = await client.patch(
        "/api/v1/organisation",
        json={"id": str(b.id), "name": "Hijacked"},
        headers=await csrf(client),
    )
    assert r.status_code == 422


# --- directly against PostgreSQL --------------------------------------------------------


async def test_rls_without_context_sees_no_tenant_rows(app_engine: AsyncEngine, factory) -> None:
    await _two_tenants(factory)
    async with app_engine.begin() as conn:
        await _as_tenant(conn, None, None)
        assert (await conn.execute(text("SELECT count(*) FROM organisations"))).scalar() == 0
        assert (await conn.execute(text("SELECT count(*) FROM organisation_users"))).scalar() == 0
        assert (await conn.execute(text("SELECT count(*) FROM audit_logs"))).scalar() == 0


async def test_rls_limits_reads_to_current_tenant(app_engine: AsyncEngine, factory) -> None:
    a, _b, ua, _ = await _two_tenants(factory)
    async with app_engine.begin() as conn:
        await _as_tenant(conn, ua.id, a.id)
        # No WHERE clause: RLS alone must filter.
        orgs = (await conn.execute(text("SELECT id FROM organisations"))).scalars().all()
        assert orgs == [a.id]
        members = (
            (await conn.execute(text("SELECT organisation_id FROM organisation_users")))
            .scalars()
            .all()
        )
        assert members == [a.id]


async def test_rls_blocks_writes_into_another_tenant(app_engine: AsyncEngine, factory) -> None:
    a, b, ua, _ub = await _two_tenants(factory)

    async with app_engine.connect() as conn:
        tx = await conn.begin()
        await _as_tenant(conn, ua.id, a.id)
        with pytest.raises(DBAPIError, match="row-level security"):
            await conn.execute(
                text(
                    "INSERT INTO organisation_users (id, organisation_id, user_id, role, status)"
                    " VALUES (gen_random_uuid(), :org, :user, 'owner', 'active')"
                ),
                {"org": b.id, "user": ua.id},
            )
        await tx.rollback()

    async with app_engine.begin() as conn:
        await _as_tenant(conn, ua.id, a.id)
        result = await conn.execute(
            text("UPDATE organisations SET name = 'Hijacked' WHERE id = :id"), {"id": b.id}
        )
        assert result.rowcount == 0  # invisible, so nothing updated

    async with app_engine.connect() as conn:
        tx = await conn.begin()
        await _as_tenant(conn, ua.id, a.id)
        with pytest.raises(DBAPIError, match="row-level security"):
            await conn.execute(
                text(
                    "INSERT INTO audit_logs (id, organisation_id, action, data)"
                    " VALUES (gen_random_uuid(), :org, 'forged', '{}')"
                ),
                {"org": b.id},
            )
        await tx.rollback()


async def test_rls_cannot_move_a_row_to_another_tenant(app_engine: AsyncEngine, factory) -> None:
    a, b, ua, _ = await _two_tenants(factory)
    async with app_engine.connect() as conn:
        tx = await conn.begin()
        await _as_tenant(conn, ua.id, a.id)
        with pytest.raises(DBAPIError, match="row-level security"):
            await conn.execute(
                text("UPDATE organisation_users SET organisation_id = :b"), {"b": b.id}
            )
        await tx.rollback()


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM audit_logs",
        "UPDATE audit_logs SET action = 'x'",
        "DELETE FROM organisations",
        "DELETE FROM organisation_users",
        "INSERT INTO organisations (id, name, slug, status, default_currency, default_timezone)"
        " VALUES (gen_random_uuid(), 'x', 'x', 'active', 'NAD', 'UTC')",
    ],
)
async def test_runtime_role_lacks_destructive_privileges(app_engine: AsyncEngine, sql) -> None:
    async with app_engine.connect() as conn:
        tx = await conn.begin()
        with pytest.raises((ProgrammingError, DBAPIError), match="permission denied"):
            await conn.execute(text(sql))
        await tx.rollback()


async def test_tenant_context_does_not_leak_between_transactions(
    app_engine: AsyncEngine, factory
) -> None:
    a, _, ua, _ = await _two_tenants(factory)
    async with app_engine.connect() as conn:
        async with conn.begin():
            await _as_tenant(conn, ua.id, a.id)
            assert (await conn.execute(text("SELECT count(*) FROM organisations"))).scalar() == 1
        # Same pooled connection, new transaction: context must be gone.
        async with conn.begin():
            assert (await conn.execute(text("SELECT count(*) FROM organisations"))).scalar() == 0
