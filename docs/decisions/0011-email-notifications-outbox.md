# 0011 — Email notifications through an outbox

**Status:** Accepted, 2026-11-23

## Context
Guests expect a booking confirmation, their invoice and a receipt by email. Sending must never block or break the action that caused it (a slow mail server must not fail a booking), must not send twice when staff click twice or a request is retried, and must leave a record of what was sent to whom. No email provider has been chosen commercially yet, so LodgeOS must work with a clearly identified mock and with any standard provider.

## Decision
- **Outbox table.** `notifications` rows are written in the same transaction as the request that asks for them, with the rendered subject, text and HTML bodies. What a guest received can be shown later exactly as sent. A row is `queued`, then `sent` or `failed`.
- **Delivery worker.** A separate process (`python -m app.cli deliver-notifications`) claims due rows with `SELECT … FOR UPDATE SKIP LOCKED`, so several workers never send the same message. It retries with backoff (1 min, 5 min, 30 min, 2 h, 6 h) and marks a row `failed` after 6 attempts, keeping the last error. The API never talks to the mail server.
- **Worker access under RLS.** The worker serves every organisation. It sets the transaction-local setting `app.notification_worker = 'on'`, which a dedicated policy on `notifications` (and only that table) honours. Only the worker module sets it; a test proves that an ordinary tenant session sees no other organisation's notifications.
- **Providers are adapters** behind one interface:
  - `mock`: the default outside production. It records messages in Redis (`mock-mailbox`) and the log, and sends nothing. Every message it handles is marked `provider = 'mock'`, so the UI says "test mode: not delivered".
  - `smtp`: standard SMTP with STARTTLS or TLS. It works with any provider that offers SMTP relay. It is tested against a local SMTP test server, not a commercial provider; that check is still to do once a provider is chosen.
  - Production refuses to start delivery with the mock provider.
- **Sender identity.** The From address is the platform's configured address with the property's name as display name. Reply-To is the property's email, so guest replies reach the lodge.
- **Idempotency.** Each send carries a client key, unique per organisation. A repeat returns the original row instead of queueing another.
- **Templates** are plain Python with `html.escape` on every value, in the Forest & Teal palette, with a text alternative. They contain no tracking pixels and no remote images.
- **Permissions** follow the subject: a booking confirmation needs `reservations.manage`, emailing an invoice needs `invoices.manage`, a receipt needs `payments.manage`. Viewing a subject's notification history needs view rights on that subject.
- **Sending is manual in this milestone** ("Email confirmation", "Email invoice", "Email receipt"). Automatic sending per property is a later setting, once properties have confirmed their wording.

## Consequences
- Email outages delay messages; they never fail bookings or payments.
- Delivery is at-least-once: if the worker stops after the provider accepted a message but before recording it, that message is sent again on restart. Duplicate confirmations are preferable to lost ones.
- Choosing a provider later means setting `LODGEOS_EMAIL_PROVIDER=smtp` and its credentials, plus one end-to-end check against that provider.
- WhatsApp and SMS can be added as further channels on the same outbox.
