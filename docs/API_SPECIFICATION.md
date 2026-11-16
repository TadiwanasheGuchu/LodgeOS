# API Specification

The authoritative, always-current schema is the OpenAPI document served by the API at `/openapi.json` (interactive docs at `/docs`) in non-production environments. This page covers conventions and a summary.

## Conventions

- Base path `/api/v1`. JSON request and response bodies.
- Authentication: session cookie `lodgeos_session` set by `POST /auth/login`.
- **CSRF:** every `POST`/`PUT`/`PATCH`/`DELETE` under `/api/` must send header `X-CSRF-Token` equal to the `lodgeos_csrf` cookie. Get the cookie with `GET /auth/csrf`. Webhooks under `/api/v1/webhooks/` are exempt and use signatures.
- The organisation is never a request parameter. It comes from the session (see `POST /auth/active-organisation`).
- Unknown fields in update bodies are rejected with 422.
- Errors: `{"detail": "<message for a person>"}`, or FastAPI's validation list for 422.
- Pagination: keyset cursors (`cursor`, `limit`), response `{items, next_cursor}`.
- Money (from Phase 2): decimal strings plus an ISO 4217 `currency`, never JSON floats.

| Status | Meaning |
|---|---|
| 401 | Not signed in or session expired |
| 403 | Signed in, but lacks permission; or CSRF failure |
| 404 | Not found, or not visible to this tenant (indistinguishable on purpose) |
| 409 | No active organisation selected |
| 422 | Validation failed |
| 429 | Throttled |
| 503 | A dependency (database/Redis) is unavailable |

## Endpoints (Phase 0)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/health/live` | — | Process is up |
| GET | `/health/ready` | — | Database and Redis reachable (503 otherwise) |
| GET | `/api/v1/auth/csrf` | — | Issues the CSRF cookie (204) |
| POST | `/api/v1/auth/login` | — | `{email, password}` → user, memberships, active organisation |
| POST | `/api/v1/auth/logout` | signed in | Revokes the session (204) |
| GET | `/api/v1/auth/me` | signed in | Current user, memberships, active organisation and permissions |
| POST | `/api/v1/auth/active-organisation` | signed in | `{organisation_id}`; 404 unless an active member |
| GET | `/api/v1/organisation` | `organisation.view` | Current organisation |
| PATCH | `/api/v1/organisation` | `organisation.manage` | Update `name`, `default_currency`, `default_timezone`, `country_code` |
| GET | `/api/v1/organisation/members` | `members.view` | Staff of the current organisation |
| GET | `/api/v1/organisation/audit-logs` | `audit.view` | Newest first; `cursor`, `limit` (1–200) |

## Role permissions (Phase 0)

| Permission | owner | manager | receptionist | housekeeping | maintenance | accountant |
|---|---|---|---|---|---|---|
| organisation.view | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| organisation.manage | ✓ | | | | | |
| members.view | ✓ | ✓ | | | | |
| members.manage | ✓ | ✓ | | | | |
| audit.view | ✓ | ✓ | | | | ✓ |
