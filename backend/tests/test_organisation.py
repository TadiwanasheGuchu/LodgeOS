from app.modules.organisations.models import Role
from tests.conftest import Factory, csrf, login


async def _signed_in(client, factory: Factory, role: Role):
    org = await factory.organisation("Etosha Edge Lodge")
    user = await factory.user()
    await factory.member(org, user, role)
    await login(client, user.email)
    return org, user


async def test_owner_updates_settings_and_change_is_audited(client, factory: Factory) -> None:
    _org, user = await _signed_in(client, factory, Role.OWNER)
    r = await client.patch(
        "/api/v1/organisation",
        json={
            "name": "Etosha Edge",
            "default_currency": "USD",
            "default_timezone": "Africa/Harare",
        },
        headers=await csrf(client),
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Etosha Edge"
    assert r.json()["default_timezone"] == "Africa/Harare"

    logs = (await client.get("/api/v1/organisation/audit-logs")).json()["items"]
    update = next(log for log in logs if log["action"] == "organisation.updated")
    assert update["actor_user_id"] == str(user.id)
    assert update["data"]["before"]["name"] == "Etosha Edge Lodge"
    assert update["data"]["after"]["default_currency"] == "USD"


async def test_settings_are_validated(client, factory: Factory) -> None:
    await _signed_in(client, factory, Role.OWNER)
    headers = await csrf(client)
    for payload in (
        {"default_timezone": "Mars/Olympus"},
        {"default_currency": "nad"},
        {"default_currency": "NAMD"},
        {"slug": "new-slug"},
        {"status": "active"},
        {"name": None},
        {"name": ""},
    ):
        r = await client.patch("/api/v1/organisation", json=payload, headers=headers)
        assert r.status_code == 422, payload


async def test_receptionist_can_view_but_not_change(client, factory: Factory) -> None:
    await _signed_in(client, factory, Role.RECEPTIONIST)
    assert (await client.get("/api/v1/organisation")).status_code == 200
    r = await client.patch(
        "/api/v1/organisation", json={"name": "Nope"}, headers=await csrf(client)
    )
    assert r.status_code == 403
    assert (await client.get("/api/v1/organisation/members")).status_code == 403
    assert (await client.get("/api/v1/organisation/audit-logs")).status_code == 403


async def test_manager_sees_members_but_cannot_change_settings(client, factory: Factory) -> None:
    await _signed_in(client, factory, Role.MANAGER)
    assert (await client.get("/api/v1/organisation/members")).status_code == 200
    r = await client.patch(
        "/api/v1/organisation", json={"name": "Nope"}, headers=await csrf(client)
    )
    assert r.status_code == 403


async def test_audit_log_pagination_does_not_skip_rows(client, factory: Factory) -> None:
    org, user = await _signed_in(client, factory, Role.OWNER)
    # 25 events in a single transaction share one timestamp.
    await factory.execute(
        "INSERT INTO audit_logs (id, organisation_id, actor_user_id, action, data)"
        " SELECT gen_random_uuid(), :org, :user, 'test.event', '{}'"
        " FROM generate_series(1, 25)",
        org=org.id,
        user=user.id,
    )
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": 7} | ({"cursor": cursor} if cursor else {})
        page = (await client.get("/api/v1/organisation/audit-logs", params=params)).json()
        seen += [i["id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 26  # 25 inserted + 1 login


async def test_health(client) -> None:
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"database": "ok", "redis": "ok"}
    assert (await client.get("/health/live")).headers["x-content-type-options"] == "nosniff"
