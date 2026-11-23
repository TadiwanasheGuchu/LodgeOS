# Integrations

Status: **none implemented.** Integrations arrive in Phases 3–5. Nothing here may be described as working until it has been tested against the real provider or a clearly identified mock (`CLAUDE.md` §16).

## Pattern every adapter follows

1. **Adapter per provider** behind a module-level interface (e.g. `PaymentGateway`, `MessageChannel`, `ChannelManager`), so providers can be swapped per organisation or per market.
2. **Inbound events** (webhooks, OTA reservations) are verified (signature, timestamp), then stored in `integration_events` with a unique `(integration_id, external_event_id)` idempotency key **before** processing. A duplicate delivery is acknowledged and ignored.
3. **Processing** happens in a Celery task inside a database transaction; failures are retried with backoff and visible in the event log.
4. **Outbound calls** carry idempotency keys where the provider supports them and are logged.
5. **Reconciliation** jobs compare our records with the provider (payments, OTA reservations) and report mismatches rather than silently fixing them.
6. Credentials are stored encrypted per organisation and never logged.

## Planned adapters and access status

| Integration | Purpose | Access requirement |
|---|---|---|
| Payment gateways | Deposits, payments, refunds | Merchant account per market; never store card data (use hosted fields / tokens) |
| Transactional email | Booking confirmations, invoices, receipts | **Built (3.5):** outbox + worker with a `mock` provider (default; sends nothing) and a standard `smtp` adapter tested against a local SMTP test server only. Needs a provider account and one live check before production (ADR-0011) |
| WhatsApp Business Platform | Guest messaging | Meta business verification and approved templates |
| SMS | Fallback messaging | Provider account |
| S3-compatible storage | Documents, images | Bucket per environment |
| Booking.com | OTA reservations, availability | Connectivity partner approval — **not assumed** |
| Expedia | OTA reservations, availability | Partner approval — **not assumed** |
| SiteMinder or equivalent | Channel management | Partner agreement |
| Google Maps | Property location | API key with restrictions |
| Accounting | Export of invoices and payments | Per provider |
