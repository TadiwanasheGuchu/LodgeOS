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
| GET | `/api/v1/organisation/audit-logs` | `audit.view` | Newest first; `cursor`, `limit` (1–200); each item includes `actor_name` |

## Endpoints (Phase 1.1–1.2)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/properties` | `properties.view` | Active properties with room and room-type counts; `include_archived` |
| POST | `/api/v1/properties` | `properties.manage` | Create; timezone/currency/country default from the organisation; 409 on slug clash |
| GET / PATCH | `/api/v1/properties/{id}` | view / manage | Read or update (including `status: archived`) |
| GET / POST | `/api/v1/properties/{id}/buildings` | view / manage | |
| PATCH | `/api/v1/buildings/{id}` | `properties.manage` | Rename, reorder, archive |
| GET / POST | `/api/v1/properties/{id}/room-types` | `rooms.view` / `rooms.manage` | List includes `room_count` |
| PATCH | `/api/v1/room-types/{id}` | `rooms.manage` | Occupancy re-validated against stored values; 409 when archiving a type with active rooms |
| GET | `/api/v1/properties/{id}/rooms` | `rooms.view` | Includes type and building names; `include_archived` |
| POST | `/api/v1/properties/{id}/rooms` | `rooms.manage` | One room |
| POST | `/api/v1/properties/{id}/rooms/bulk` | `rooms.manage` | `{numbers[], room_type_id, building_id?, floor?}`; all or nothing; 409 lists existing numbers |
| PATCH | `/api/v1/rooms/{id}` | `rooms.manage` | Number, type, building, floor, notes, status |
| POST | `/api/v1/rooms/{id}/housekeeping` | `rooms.housekeeping_update` | `{housekeeping_status}` |
| POST | `/api/v1/rooms/{id}/maintenance` | `rooms.maintenance_update` | `{maintenance_status, reason}`; reason required unless `none` |

IDs belonging to another organisation return 404, exactly like IDs that do not exist.

## Role permissions

| Permission | owner | manager | receptionist | housekeeping | maintenance | accountant |
|---|---|---|---|---|---|---|
| organisation.view | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| organisation.manage | ✓ | | | | | |
| members.view | ✓ | ✓ | | | | |
| members.manage | ✓ | ✓ | | | | |
| audit.view | ✓ | ✓ | | | | ✓ |
| properties.view | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| properties.manage | ✓ | ✓ | | | | |
| rooms.view | ✓ | ✓ | ✓ | ✓ | ✓ | |
| rooms.manage | ✓ | ✓ | | | | |
| rooms.housekeeping_update | ✓ | ✓ | ✓ | ✓ | | |
| rooms.maintenance_update | ✓ | ✓ | | | ✓ | |
