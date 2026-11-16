# 0002 — Tenant isolation: server-side session plus PostgreSQL RLS

**Status:** Accepted, 2026-11-16

## Context
Many hospitality businesses share one database. A leak of guest data or financial records between tenants would be a serious breach. Application-level `WHERE organisation_id = ...` filters are necessary but one forgotten filter is enough to leak.

## Decision
- The tenant is the organisation. The active organisation is stored on the server-side session and changed only after a membership check. Organisation IDs from the client are never used for scoping.
- Every request runs in one transaction that sets transaction-local `app.current_org_id` and `app.current_user_id`.
- Every tenant-owned table has RLS policies comparing `organisation_id` with `app_current_org_id()`. The API connects as `lodgeos_app`, which owns nothing and has `NOBYPASSRLS`. Migrations use `lodgeos_owner`.
- New tables use `migrations/helpers.py::enable_tenant_rls` unless a custom policy is documented.

## Consequences
- A missing filter in application code returns no foreign rows instead of leaking them.
- Context must be set inside the transaction; `set_config(..., true)` makes it safe with connection pooling (tested).
- `INSERT ... RETURNING` is checked against SELECT policies too. Rows deliberately unreadable to the app (audit events without an organisation) must not use eager server defaults.
- Background jobs must set the tenant context explicitly before touching tenant tables.
