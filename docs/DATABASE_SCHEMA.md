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

## Tables (Phase 1.1–1.2)

All four use `enable_tenant_rls` (SELECT, INSERT, UPDATE for the app role; no DELETE). Setup records are archived (`status = 'archived'`), never deleted.

**Same-tenant, same-property integrity.** Composite unique keys and foreign keys make cross-property references impossible at the database level:
- `properties` has `UNIQUE (id, organisation_id)`; children reference `(property_id, organisation_id)`.
- `room_types` and `buildings` have `UNIQUE (id, property_id)`; `rooms` references `(room_type_id, property_id)` and `(building_id, property_id)`.

### `properties`
| Column | Type | Notes |
|---|---|---|
| id, organisation_id | uuid | |
| name | varchar(200) | |
| slug | varchar(63) | unique per organisation |
| property_type | varchar(32) | guesthouse, boutique_hotel, hotel, lodge, safari_lodge, resort, serviced_apartments, other |
| status | varchar(20) | active \| archived |
| timezone | varchar(64) | IANA; defaults from the organisation |
| currency | varchar(3) | ISO 4217; defaults from the organisation |
| country_code | varchar(2) null | |
| address_line1/2, city, region, postal_code, phone, email | | optional |
| check_in_time, check_out_time | time | wall-clock time in the property's timezone |

### `buildings`
`id, organisation_id, property_id, name (unique per property), description, sort_order, status`.

### `room_types`
| Column | Notes |
|---|---|
| name, code | both unique per property; code `^[A-Z0-9][A-Z0-9-]{0,9}$` |
| base_occupancy | guests included in the base rate (≥ 1) |
| max_occupancy, max_adults, max_children | checked: max ≥ base, adults ≤ max, children ≤ max |
| bed_configuration, description, sort_order, status | |

### `rooms`
| Column | Notes |
|---|---|
| number | unique per property |
| room_type_id, building_id (null) | must belong to the same property (composite FKs) |
| floor, notes, status | |
| housekeeping_status | dirty \| clean \| inspected — cleanliness only |
| housekeeping_updated_at / _by | |
| maintenance_status | none \| out_of_service \| out_of_order |
| maintenance_reason | required unless status is `none` (CHECK) |
| maintenance_updated_at / _by | |

Occupancy is deliberately not stored: it will be derived from reservations (Phase 2), so it cannot drift from bookings. Sellability will combine room status, maintenance status and allocations.

## Tables (Phase 1.3)

`organisation_users.role` was removed; roles now live in these tables (ADR-0006). The migration converted each membership's role into an organisation-wide `user_roles` row, and its downgrade restores the column.

| Table | Key columns | RLS / privileges |
|---|---|---|
| `permissions` | `code` unique, `description` | Global catalogue; app role SELECT only |
| `roles` | `organisation_id`, `key` (system role key or NULL), `name`, `is_system`; unique `(organisation_id, name)` and `(organisation_id, key)` | Tenant RLS, plus read of roles the user holds anywhere |
| `role_permissions` | PK `(role_id, permission_id)`; `(role_id, organisation_id)` → `roles` | Tenant RLS; SELECT, INSERT, DELETE |
| `user_roles` | `membership_id`, `role_id`, `property_id` (NULL = all properties), `created_by`; unique `(membership_id, role_id, property_id)` with NULLS NOT DISTINCT; composite FKs keep membership, role and property in one organisation | Tenant RLS, plus read of the user's own rows in any organisation; SELECT, INSERT, DELETE |
| `invitations` | `email`, `full_name`, `role_id`, `property_id`, `token_hash` (SHA-256, unique), `expires_at`, `accepted_at`/`by`, `revoked_at`, `created_by` | Tenant RLS. `invitation_for_token(bytea)` is SECURITY DEFINER and returns only ids, for use before sign-in |

## Tables (Phase 1.4)

Money is `NUMERIC(12,2)`; tax rates are `NUMERIC(7,4)` percentages (ADR-0007). All four tables use tenant RLS and composite foreign keys to the same property.

| Table | Key columns | Notes |
|---|---|---|
| `taxes` | `name` (unique per property), `rate_percent` (0 < rate < 100), `sort_order`, `status` | Archived taxes are not charged; no DELETE |
| `rate_plans` | `name`, `code` (unique per property), `kind` (standard, corporate, promotional, package), `meal_plan`, `currency`, `prices_include_tax`, `min_stay_nights`, `max_stay_nights`, `stay_from`, `stay_to`, `status` | Currency copied from the property and stored; no DELETE |
| `rate_plan_prices` | unique `(rate_plan_id, room_type_id)`; `base_price`, `weekend_price`, `extra_adult_price`, `extra_child_price` (all ≥ 0) | DELETE allowed (setup, not history) |
| `seasonal_rates` | `rate_plan_id`, `room_type_id`, `name`, `start_date`, `end_date` (inclusive), same four prices | **Exclusion constraint** `ex_seasonal_rates_no_overlap` (btree_gist): no two seasons for one plan and room type share a night |

`properties.weekend_nights smallint[]` (default `{5,6}`, Friday and Saturday nights) selects which nights use weekend prices.

## Tables (Phase 2.1)

All use tenant RLS; none can be deleted by the app role (ADR-0008).

| Table | Key columns | Notes |
|---|---|---|
| `guests` | `first_name`, `last_name`, `email`, `phone`, `country_code`, `notes` | Organisation-wide, so returning guests are recognised at every property |
| `reservations` | `reference` (unique per organisation), `status`, `source`, `guest_id`, `check_in`, `check_out`, `currency`, `total_amount`, `tax_amount`, `notes`, `cancellation_reason`, `created_by` | CHECK: cancelled ⇔ reason present; check_out > check_in |
| `reservation_rooms` | `room_type_id`, `room_id` (null until allocated), `rate_plan_id`, dates and status copied from the reservation, `adults`, `children`, `total_amount`, `tax_amount`, `price_snapshot` (JSONB) | **Exclusion constraint** `ex_reservation_rooms_no_double_booking`; partial index `ix_reservation_rooms_inventory` for availability |
| `reservation_status_history` | `from_status`, `to_status`, `reason`, `changed_by`, `changed_at` | INSERT and SELECT only |

`rooms` gained `UNIQUE (id, property_id)` for the composite foreign key from `reservation_rooms`.

## Tables (Phase 3.1)

Both use tenant RLS; the app role cannot delete from either.

| Table | Key columns | Notes |
|---|---|---|
| `maintenance_tickets` | `property_id`, `room_id` (nullable, composite FK `(room_id, property_id)`), `location`, `title`, `description`, `priority` (low, normal, urgent), `status` (open, in_progress, resolved, cancelled), `reported_by`, `assigned_to`, `resolution`, `closed_at` | CHECK: `closed_at` set exactly when resolved or cancelled |
| `room_blocks` | `room_id`, `ticket_id`, `start_date`, `end_date` (exclusive), `reason`, `status` (active, released), `created_by` | CHECK `end_date > start_date`; partial index `ix_room_blocks_active`. Active blocks are subtracted from availability per night; created under the room-type lock (ADR-0008) |

## Tables (Phase 3.2)

| Table | Key columns | Notes |
|---|---|---|
| `housekeeping_tasks` | `property_id`, `room_id` (composite FK), `task_date`, `kind` (departure, stayover, arrival, vacant), `status` (pending, in_progress, done, declined), `assigned_to`, `note`, `started_at`, `completed_at`, `completed_by` | Tenant RLS. UNIQUE `(room_id, task_date)`; CHECK `completed_at` set exactly when done or declined; declined needs a note. Written only when someone acts on a room; the list itself is derived from bookings |

## Planned tables

Next: `invoices`, `invoice_items`, `credit_notes` (3.3), `payments`, `payment_allocations`, `refunds` (3.4), `notifications` (3.5).
