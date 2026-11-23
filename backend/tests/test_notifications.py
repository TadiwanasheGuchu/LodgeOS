"""Email notifications through the outbox (ADR-0011)."""

import asyncio
import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import Settings
from app.core.redis import get_redis
from app.modules.notifications import service
from app.modules.notifications.providers import (
    MOCK_MAILBOX,
    DeliveryError,
    MockProvider,
    OutgoingEmail,
    SmtpProvider,
)
from app.modules.organisations.models import Role
from tests.conftest import login
from tests.test_invoices import _booked, _invoice_for, _issue
from tests.test_reservations import _booking, _post, _setup


def key() -> str:
    return uuid.uuid4().hex


async def _mailbox() -> list[dict[str, str]]:
    return [json.loads(m) for m in await get_redis().lrange(MOCK_MAILBOX, 0, -1)]


async def test_booking_confirmation_is_queued_once_and_delivered(
    client, factory, app_engine: AsyncEngine
) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    body = _booking(rt, plan, "2027-01-10", "2027-01-13", last="<script>alert(1)</script>")
    res = (await _post(client, f"/api/v1/properties/{prop['id']}/reservations", body)).json()
    url = f"/api/v1/reservations/{res['id']}/email-confirmation"
    k = key()
    first = await _post(client, url, {"idempotency_key": k})
    assert first.status_code == 202, first.text
    n = first.json()
    assert (n["recipient"], n["status"], n["kind"]) == (
        "ndeshi@example.com",
        "queued",
        "booking_confirmation",
    )
    assert n["title"] == f"Your booking {res['reference']} is confirmed · Epupa Camp"
    assert "Arrival: Sunday 10 January 2027, from 14:00" in n["body_text"]
    assert "Total, taxes included: NAD 3 000.00" in n["body_text"]
    again = await _post(client, url, {"idempotency_key": k})
    assert (again.status_code, again.json()["id"]) == (200, n["id"])

    # The worker delivers it through the mock provider; nothing leaves the machine.
    sm = async_sessionmaker(app_engine, expire_on_commit=False)
    assert await service.deliver_due(sm, MockProvider()) == 1
    assert await service.deliver_due(sm, MockProvider()) == 0
    [mail] = await _mailbox()
    assert (mail["to"], mail["from_name"]) == ("ndeshi@example.com", "Epupa Camp")
    # Guest-supplied text is escaped in the HTML body.
    assert "<script>" not in mail["html"] and "&lt;script&gt;" in mail["html"]
    listed = (
        await client.get(
            "/api/v1/notifications", params={"subject_type": "reservation", "subject_id": res["id"]}
        )
    ).json()
    assert [(x["status"], x["provider"], x["attempts"]) for x in listed] == [("sent", "mock", 1)]


async def test_invoice_and_receipt_emails(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    draft = await _invoice_for(client, prop, await _booked(client, prop, rt, plan))
    r = await _post(client, f"/api/v1/invoices/{draft['id']}/email", {"idempotency_key": key()})
    assert r.status_code == 409
    inv = await _issue(client, draft)
    pay = (
        await _post(
            client,
            f"/api/v1/properties/{prop['id']}/payments",
            {
                "method": "card",
                "amount": "1000.00",
                "invoice_id": inv["id"],
                "reference": "SLIP-77",
                "idempotency_key": key(),
            },
        )
    ).json()
    r = await _post(
        client,
        f"/api/v1/invoices/{inv['id']}/email",
        {"to": "accounts@namib-mining.example", "idempotency_key": key()},
    )
    assert r.status_code == 202, r.text
    mail = r.json()
    assert mail["recipient"] == "accounts@namib-mining.example"
    assert mail["title"] == "Invoice INV-000001 from Epupa Camp"
    assert "Paid: NAD -1 000.00" in mail["body_text"]
    assert "Balance due: NAD 2 000.00" in mail["body_text"]

    r = await _post(
        client, f"/api/v1/payments/{pay['id']}/email-receipt", {"idempotency_key": key()}
    )
    assert r.status_code == 202, r.text
    receipt = r.json()
    assert receipt["title"] == "Receipt: NAD 1 000.00 received · Epupa Camp"
    assert "Invoice INV-000001: NAD 1 000.00" in receipt["body_text"]
    assert "Reference: SLIP-77" in receipt["body_text"]


async def test_no_address_on_file_needs_one(client, factory) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    body = _booking(rt, plan)
    body["guest"].pop("email")
    res = (await _post(client, f"/api/v1/properties/{prop['id']}/reservations", body)).json()
    url = f"/api/v1/reservations/{res['id']}/email-confirmation"
    r = await _post(client, url, {"idempotency_key": key()})
    assert r.status_code == 422
    assert r.json()["detail"] == "There is no email address on file. Enter one to send to."
    r = await _post(client, url, {"to": "not-an-email", "idempotency_key": key()})
    assert r.status_code == 422
    r = await _post(client, url, {"to": "guest@example.com", "idempotency_key": key()})
    assert r.status_code == 202


class FailingProvider:
    name = "failing"

    async def send(self, message: OutgoingEmail) -> str:
        raise DeliveryError("421 try again later")


async def test_failed_delivery_is_retried_then_marked_failed(
    client, factory, app_engine: AsyncEngine
) -> None:
    _, prop, rt, plan, _ = await _setup(client, factory)
    res = (
        await _post(client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan))
    ).json()
    n = (
        await _post(
            client,
            f"/api/v1/reservations/{res['id']}/email-confirmation",
            {"idempotency_key": key()},
        )
    ).json()
    sm = async_sessionmaker(app_engine, expire_on_commit=False)
    assert await service.deliver_due(sm, FailingProvider()) == 1
    # Not due again until the backoff has passed.
    assert await service.deliver_due(sm, FailingProvider()) == 0
    for _ in range(service.MAX_ATTEMPTS - 1):
        await factory.execute(
            "UPDATE notifications SET next_attempt_at = now() - interval '1 second' WHERE id = :id",
            id=uuid.UUID(n["id"]),
        )
        await service.deliver_due(sm, FailingProvider())
    [row] = (
        await client.get(
            "/api/v1/notifications", params={"subject_type": "reservation", "subject_id": res["id"]}
        )
    ).json()
    assert (row["status"], row["attempts"], row["last_error"]) == (
        "failed",
        service.MAX_ATTEMPTS,
        "421 try again later",
    )


async def test_tenants_cannot_see_each_others_outbox(
    client, factory, app_engine: AsyncEngine
) -> None:
    org, prop, rt, plan, _ = await _setup(client, factory)
    res = (
        await _post(client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan))
    ).json()
    await _post(
        client, f"/api/v1/reservations/{res['id']}/email-confirmation", {"idempotency_key": key()}
    )
    other = await factory.organisation("Elsewhere")

    async def visible(org_id: uuid.UUID | None, worker: bool) -> int:
        async with app_engine.connect() as conn:
            await conn.execute(
                text("SELECT set_config('app.current_org_id', :o, true)"),
                {"o": str(org_id) if org_id else ""},
            )
            if worker:
                await conn.execute(text("SELECT set_config('app.notification_worker', 'on', true)"))
            count = await conn.scalar(text("SELECT count(*) FROM notifications"))
            await conn.rollback()
            return int(count or 0)

    assert await visible(org.id, worker=False) == 1
    assert await visible(other.id, worker=False) == 0
    assert await visible(None, worker=False) == 0
    assert await visible(None, worker=True) == 1


async def test_permissions(client, factory) -> None:
    org, prop, rt, plan, _ = await _setup(client, factory)
    res = (
        await _post(client, f"/api/v1/properties/{prop['id']}/reservations", _booking(rt, plan))
    ).json()
    keeper = await factory.user()
    await factory.member(org, keeper, Role.HOUSEKEEPING)
    await login(client, keeper.email)
    url = f"/api/v1/reservations/{res['id']}/email-confirmation"
    assert (await _post(client, url, {"idempotency_key": key()})).status_code == 403
    r = await client.get(
        "/api/v1/notifications", params={"subject_type": "reservation", "subject_id": res["id"]}
    )
    assert r.status_code == 403

    front = await factory.user()
    await factory.member(org, front, Role.RECEPTIONIST)
    await login(client, front.email)
    assert (await _post(client, url, {"idempotency_key": key()})).status_code == 202

    stranger_org = await factory.organisation("Elsewhere")
    stranger = await factory.user()
    await factory.member(stranger_org, stranger, Role.OWNER)
    await login(client, stranger.email)
    assert (await _post(client, url, {"idempotency_key": key()})).status_code == 404


async def _fake_smtp_server() -> tuple[asyncio.AbstractServer, int, list[str]]:
    """A minimal SMTP server for testing the adapter's protocol handling. It accepts one
    message per connection and records the DATA section."""
    received: list[str] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 test.local ESMTP\r\n")
        await writer.drain()
        while line := await reader.readline():
            cmd = line.decode().strip().upper()
            if cmd.startswith(("EHLO", "HELO")):
                writer.write(b"250-test.local\r\n250 8BITMIME\r\n")
            elif cmd.startswith(("MAIL", "RCPT", "RSET", "NOOP")):
                writer.write(b"250 OK\r\n")
            elif cmd == "DATA":
                writer.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                await writer.drain()
                lines = []
                while (data := await reader.readline()) != b".\r\n":
                    lines.append(data.decode())
                received.append("".join(lines))
                writer.write(b"250 OK queued\r\n")
            elif cmd == "QUIT":
                writer.write(b"221 Bye\r\n")
                await writer.drain()
                break
            else:
                writer.write(b"502 Not implemented\r\n")
            await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port, received


async def test_smtp_adapter_against_a_local_test_server() -> None:
    server, port, received = await _fake_smtp_server()
    settings = Settings(
        email_provider="smtp",
        smtp_host="127.0.0.1",
        smtp_port=port,
        smtp_security="none",
        email_from_address="bookings@lodgeos.example",
    )
    message = OutgoingEmail(
        to="guest@example.com",
        from_address="bookings@lodgeos.example",
        from_name="Epupa Camp",
        reply_to="stay@epupa.example",
        subject="Your booking LOS-ABC123 is confirmed",
        text="Dear guest,\nSee you soon.\n",
        html="<p>Dear guest,</p>",
    )
    async with server:
        message_id = await SmtpProvider(settings).send(message)
    assert message_id.startswith("<") and message_id.endswith("@lodgeos.example>")
    [raw] = received
    assert "From: Epupa Camp <bookings@lodgeos.example>" in raw
    assert "Reply-To: stay@epupa.example" in raw
    assert "Subject: Your booking LOS-ABC123 is confirmed" in raw
    assert "multipart/alternative" in raw

    # A server that is not there is a delivery error the worker can retry.
    closed = Settings(
        email_provider="smtp", smtp_host="127.0.0.1", smtp_port=port, smtp_security="none"
    )
    try:
        await SmtpProvider(closed).send(message)
    except DeliveryError as exc:
        assert "ConnectionRefusedError" in str(exc)
    else:
        raise AssertionError("expected a delivery error")
