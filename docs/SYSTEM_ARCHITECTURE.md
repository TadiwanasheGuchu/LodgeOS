# System Architecture

## Shape

LodgeOS is a **modular monolith**: one FastAPI application and one PostgreSQL database, divided into domain modules with explicit boundaries. Microservices are deliberately out of scope until a measured need appears (ADR-0001).

```
                     ┌──────────────────────────── Next.js (frontend/) ───────────────────────────┐
 Browsers ─ HTTPS ─► │ marketing · platform admin · organisation admin · property ops ·          │
                     │ public booking engine · guest portal                                       │
                     └───────────────────────────────┬────────────────────────────────────────────┘
                                                     │ REST + cookies (CSRF-protected)
                     ┌───────────────────────────────▼────────────────────────────────────────────┐
                     │ FastAPI (backend/app)                                                      │
                     │   core/      config · db + tenant context · security · CSRF · rate limit   │
                     │   modules/   auth · organisations · audit · (properties, reservations, …)  │
                     └──────┬──────────────────────────────┬─────────────────────────┬────────────┘
                            │ lodgeos_app role (RLS)       │                         │
                     ┌──────▼──────┐               ┌───────▼──────┐          ┌───────▼──────┐
                     │ PostgreSQL  │               │    Redis     │          │ Celery (later)│
                     └─────────────┘               └──────────────┘          └──────────────┘
```

## Backend layout

```
backend/
  app/
    core/                 cross-cutting infrastructure, no business logic
    modules/<domain>/     models.py · schemas.py · service.py · router.py · deps.py
    models.py             imports every model (for Alembic)
    cli.py                operator commands (run as lodgeos_owner)
  migrations/             Alembic; helpers.py has enable_tenant_rls()
  tests/                  pytest against real PostgreSQL and Redis
```

Rules for modules:
- A module's `router` calls its own `service`. Cross-module calls go through the other module's `service` functions, never its router or private helpers.
- Business rules live in services, not routers, so they can be reused by Celery tasks and integrations.
- Every tenant-owned table has an `organisation_id` column and RLS (see below).

## Frontend layout

```
frontend/
  src/proxy.ts                 per-request CSP nonce and security headers
  src/app/sign-in/             sign-in (public)
  src/app/select-organisation/ organisation picker
  src/app/(app)/               signed-in area: layout.tsx loads the user, AppShell renders
                               role-filtered navigation; pages: overview, team, activity, settings
  src/components/ui/           Button, Field/Input/Select, Alert
  src/lib/server/api.ts        server-side API calls (forwards cookies; redirects on 401)
  src/lib/api-client.ts        browser API calls (adds CSRF header; maps errors)
  e2e/                         Playwright tests against the real API
```

- The browser only talks to the Next.js origin; `next.config.ts` rewrites `/api/*` to the FastAPI service (ADR-0005).
- Pages are server-rendered per request. Server components read the session through the API, never directly from the database.
- Navigation lists only screens that exist and that the role may open. The API still enforces every permission.

## Request lifecycle

1. `CORSMiddleware` → `CSRFMiddleware` (double-submit token for unsafe methods under `/api/`).
2. `get_db` opens **one transaction per request** and clears the tenant context.
3. `get_auth` resolves the session cookie (hashed lookup, idle and absolute expiry), loads the user, re-verifies the active membership, and sets `app.current_user_id` / `app.current_org_id` for the transaction.
4. `require_permission(...)` checks the role's permissions.
5. The handler runs; audit events are written in the same transaction, so they commit or roll back with the change.

## Multi-tenancy (ADR-0002)

- The tenant is the **organisation**. Properties (Phase 1) belong to an organisation.
- The active organisation is stored **server-side on the session** and changed only through `POST /api/v1/auth/active-organisation`, which verifies membership. The API never accepts an organisation ID from the client for scoping.
- PostgreSQL RLS is a second, independent layer. The API connects as `lodgeos_app` (`NOBYPASSRLS`, owns nothing). Policies compare rows against `app_current_org_id()` / `app_current_user_id()`, which read transaction-local settings. A missing context yields `NULL` and matches nothing.
- Migrations and operator commands use `lodgeos_owner`, which owns the tables and therefore bypasses RLS. It is never used by the running API.
- `lodgeos_app` has no `DELETE` on any table so far, and only `INSERT`/`SELECT` on `audit_logs`.

## Data-consistency principles for upcoming modules

- Booking and availability changes run in a single database transaction with row locks or exclusion constraints. Caches never decide availability.
- Physical room allocations will use a PostgreSQL exclusion constraint on `(room_id, daterange)` so overlap is impossible at the database level.
- Money is `NUMERIC` with an explicit currency column. Posted financial records are never updated or deleted; corrections are reversals, adjustments and credit notes.
- External events (OTA bookings, payment webhooks) are stored in `integration_events` with a unique idempotency key before processing.
