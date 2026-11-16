from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.security import hash_password, hash_token, verify_password
from app.modules.organisations.models import Role
from tests.conftest import PASSWORD, Factory, csrf, login

# --- password hashing -------------------------------------------------------------------


def test_password_hash_is_argon2id_and_verifies() -> None:
    h = hash_password("a long enough password")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "a long enough password")
    assert not verify_password(h, "wrong password")
    assert not verify_password(None, "anything")
    assert not verify_password("not-a-hash", "anything")


def test_session_tokens_are_stored_hashed() -> None:
    assert hash_token("abc") != b"abc"
    assert len(hash_token("abc")) == 32


# --- sign in ----------------------------------------------------------------------------


async def test_login_with_one_organisation_starts_in_it(client, factory: Factory) -> None:
    org = await factory.organisation("Kalahari Rest")
    user = await factory.user("Owner@Example.com")
    await factory.member(org, user)

    r = await login(client, "owner@example.com")  # email is case-insensitive
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == "Owner@Example.com"
    assert body["active_organisation"]["id"] == str(org.id)
    assert body["active_organisation"]["role"] == "owner"
    assert "organisation.manage" in body["active_organisation"]["permissions"]

    set_cookie = r.headers.get_list("set-cookie")
    session_cookie = next(c for c in set_cookie if c.startswith("lodgeos_session="))
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["active_organisation"]["id"] == str(org.id)


async def test_wrong_password_and_unknown_email_get_the_same_answer(
    client, factory: Factory, owner_engine: AsyncEngine
) -> None:
    user = await factory.user("someone@example.com")
    wrong = await login(client, "someone@example.com", "not the password")
    unknown = await login(client, "nobody@example.com", "not the password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()

    async with owner_engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT actor_user_id, action FROM audit_logs ORDER BY created_at")
            )
        ).all()
    # Failures are audited even though the request fails.
    assert [r.action for r in rows] == ["auth.login_failed", "auth.login_failed"]
    assert {r.actor_user_id for r in rows} == {user.id, None}


async def test_inactive_user_cannot_sign_in(client, factory: Factory) -> None:
    await factory.user("gone@example.com", active=False)
    r = await login(client, "gone@example.com")
    assert r.status_code == 401


async def test_login_is_throttled_per_email(client, factory: Factory) -> None:
    await factory.user("target@example.com")
    for _ in range(10):
        r = await login(client, "target@example.com", "guess")
        assert r.status_code == 401
    r = await login(client, "target@example.com", PASSWORD)
    assert r.status_code == 429  # even the right password is refused while throttled


async def test_requests_without_session_are_rejected(client) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.get("/api/v1/organisation")).status_code == 401


# --- CSRF -------------------------------------------------------------------------------


async def test_state_changing_requests_need_csrf_token(client, factory: Factory) -> None:
    await factory.user("a@example.com")
    r = await client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": PASSWORD}
    )
    assert r.status_code == 403

    headers = await csrf(client)
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": PASSWORD},
        headers={"X-CSRF-Token": headers["X-CSRF-Token"] + "x"},
    )
    assert r.status_code == 403


# --- sessions ---------------------------------------------------------------------------


async def test_logout_revokes_the_session(client, factory: Factory) -> None:
    org = await factory.organisation()
    user = await factory.user()
    await factory.member(org, user)
    await login(client, user.email)
    old_cookie = client.cookies["lodgeos_session"]

    r = await client.post("/api/v1/auth/logout", headers=await csrf(client))
    assert r.status_code == 204

    # Replaying the old cookie must not work, even if the browser kept it.
    client.cookies.set("lodgeos_session", old_cookie)
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_idle_and_absolute_expiry(client, factory: Factory) -> None:
    user = await factory.user()
    await login(client, user.email)
    assert (await client.get("/api/v1/auth/me")).status_code == 200

    stale = datetime.now(UTC) - timedelta(hours=13)
    await factory.execute("UPDATE user_sessions SET last_seen_at = :t", t=stale)
    assert (await client.get("/api/v1/auth/me")).status_code == 401

    await factory.execute(
        "UPDATE user_sessions SET last_seen_at = now(), expires_at = now() - interval '1 second'"
    )
    assert (await client.get("/api/v1/auth/me")).status_code == 401


# --- organisations ----------------------------------------------------------------------


async def test_user_with_several_organisations_must_choose(client, factory: Factory) -> None:
    a = await factory.organisation("Alpha Lodge")
    b = await factory.organisation("Bravo Guesthouse")
    user = await factory.user()
    await factory.member(a, user, Role.OWNER)
    await factory.member(b, user, Role.RECEPTIONIST)

    r = await login(client, user.email)
    assert r.json()["active_organisation"] is None
    assert {m["organisation_name"] for m in r.json()["memberships"]} == {
        "Alpha Lodge",
        "Bravo Guesthouse",
    }
    assert (await client.get("/api/v1/organisation")).status_code == 409

    r = await client.post(
        "/api/v1/auth/active-organisation",
        json={"organisation_id": str(b.id)},
        headers=await csrf(client),
    )
    assert r.status_code == 200
    assert r.json()["active_organisation"]["role"] == "receptionist"
    org = await client.get("/api/v1/organisation")
    assert org.json()["name"] == "Bravo Guesthouse"


async def test_cannot_switch_into_an_organisation_you_do_not_belong_to(
    client, factory: Factory
) -> None:
    mine = await factory.organisation("Mine")
    theirs = await factory.organisation("Theirs")
    user = await factory.user()
    await factory.member(mine, user)

    await login(client, user.email)
    r = await client.post(
        "/api/v1/auth/active-organisation",
        json={"organisation_id": str(theirs.id)},
        headers=await csrf(client),
    )
    assert r.status_code == 404
    me = await client.get("/api/v1/auth/me")
    assert me.json()["active_organisation"]["id"] == str(mine.id)


async def test_disabling_a_membership_takes_effect_immediately(client, factory: Factory) -> None:
    org = await factory.organisation()
    user = await factory.user()
    member = await factory.member(org, user, Role.MANAGER)
    await login(client, user.email)
    assert (await client.get("/api/v1/organisation/members")).status_code == 200

    await factory.execute(
        "UPDATE organisation_users SET status = 'disabled' WHERE id = :id", id=member.id
    )
    assert (await client.get("/api/v1/organisation/members")).status_code == 409
    me = await client.get("/api/v1/auth/me")
    assert me.json()["active_organisation"] is None
    assert me.json()["memberships"] == []


async def test_suspended_organisation_is_not_accessible(client, factory: Factory) -> None:
    org = await factory.organisation()
    user = await factory.user()
    await factory.member(org, user)
    await login(client, user.email)

    await factory.execute("UPDATE organisations SET status = 'suspended' WHERE id = :id", id=org.id)
    assert (await client.get("/api/v1/organisation")).status_code == 409


async def test_login_fails_closed_when_redis_is_unavailable(
    client, factory: Factory, monkeypatch
) -> None:
    from redis.asyncio import Redis

    from app.core import rate_limit

    await factory.user("closed@example.com")
    headers = await csrf(client)  # fetch before breaking Redis
    unreachable = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    monkeypatch.setattr(rate_limit, "get_redis", lambda: unreachable)
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "closed@example.com", "password": PASSWORD},
        headers=headers,
    )
    assert r.status_code == 503
    assert "lodgeos_session" not in r.headers.get("set-cookie", "")
    await unreachable.aclose()
