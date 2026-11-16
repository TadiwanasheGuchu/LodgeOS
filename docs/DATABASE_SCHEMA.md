# Database Schema

PostgreSQL 17. All primary keys are UUIDs. Timestamps are `timestamptz`. Migrations live in `backend/migrations/` and every migration must downgrade cleanly (the test suite runs upgrade → downgrade → upgrade).

## Roles

| Role | Used by | RLS applies | Notes |
|---|---|---|---|
| `lodgeos_owner` | Alembic, operator CLI | No (table owner) | Never used by the running API |
| `lodgeos_app` | API at runtime | Yes (`NOBYPASSRLS`) | Explicit grants per table; no `DELETE` so far |

## Tenant context functions

| Function | Returns |
|---|---|
| `app_current_org_id()` | `app.current_org_id` setting as `uuid`, or `NULL` |
| `app_current_user_id()` | `app.current_user_id` setting as `uuid`, or `NULL` |

Both are set per transaction by `app.core.db.set_tenant_context`.

## Tables (Phase 0)

### `organisations` — tenants
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| name | varchar(200) | |
| slug | varchar(63) unique | `^[a-z0-9]+(-[a-z0-9]+)*$` |
| status | varchar(20) | `active` \| `suspended` |
| default_currency | char-like varchar(3) | ISO 4217, `^[A-Z]{3}$` |
| default_timezone | varchar(64) | IANA name, validated by the API |
| country_code | varchar(2) null | ISO 3166-1 alpha-2 |
| created_at, updated_at | timestamptz | |

RLS: `SELECT` the current organisation or any where the current user has an active membership. `UPDATE` only the current organisation. No `INSERT`/`DELETE` for the app role.

### `users` — global identities
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| email | varchar(320) | unique on `lower(email)` |
| full_name | varchar(200) | |
| password_hash | varchar(255) null | Argon2id; null for future external-IdP accounts |
| is_active | boolean | |
| last_login_at | timestamptz null | |

No RLS: a user can belong to several organisations. Staff details are exposed only through organisation-scoped endpoints.

### `organisation_users` — memberships
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organisation_id | uuid FK → organisations (RESTRICT) | indexed |
| user_id | uuid FK → users (RESTRICT) | indexed |
| role | varchar(32) | `owner`, `manager`, `receptionist`, `housekeeping`, `maintenance`, `accountant` |
| status | varchar(20) | `active` \| `disabled` |

Unique `(organisation_id, user_id)`. RLS: read rows of the current organisation or the current user's own memberships; insert/update only within the current organisation.

### `user_sessions`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| token_hash | bytea(32) unique | SHA-256 of the cookie token |
| user_id | uuid FK → users (CASCADE) | |
| active_organisation_id | uuid FK → organisations (SET NULL) null | set only by the server |
| created_at, last_seen_at, expires_at, revoked_at | timestamptz | |
| ip_address | inet null | |
| user_agent | varchar(512) null | |

No RLS: looked up by token hash before any tenant context exists.

### `audit_logs` — append-only
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| organisation_id | uuid FK null | null for events outside a tenant (e.g. failed sign-in) |
| actor_user_id | uuid FK null | |
| action | varchar(100) | e.g. `auth.login`, `organisation.updated` |
| entity_type, entity_id | | what was affected |
| data | jsonb | IDs and changed fields only; never secrets |
| ip_address | inet null | |
| created_at | timestamptz | indexed with organisation_id |

App role: `INSERT`, `SELECT` only. RLS: read the current organisation's events; insert for the current organisation or with a null organisation.

## Planned tables

The full list from `CLAUDE.md` §7 is added module by module. Phase 1 next: `properties`, `buildings`, `room_types`, `rooms`, `roles`, `permissions`, `user_roles`, `rate_plans`, `seasonal_rates`.
