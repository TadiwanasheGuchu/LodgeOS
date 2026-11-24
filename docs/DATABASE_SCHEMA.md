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

## Tables (Phase 3.3)

All use tenant RLS (ADR-0009). Amounts are NUMERIC(12,2); every line and document satisfies net + tax = total (CHECK).

| Table | Key columns | Notes |
|---|---|---|
| `document_sequences` | PK (`organisation_id`, `kind`), `next_number` | Gapless numbering; row locked while issuing |
| `invoices` | `property_id`, `reservation_id` (composite FK), `guest_id`, `number` (UNIQUE per organisation), `status` (draft, issued, discarded), `currency`, `issue_date`, `due_date`, `bill_to_name`, `bill_to_details`, `notes`, `net_total`, `tax_total`, `total`, `issued_at`, `issued_by`, `created_by` | CHECK: issued ⇔ number, issue date and issued_at set. Trigger `invoices_guard`: rows that are not drafts cannot be updated. No DELETE for the app role |
| `invoice_items` | `invoice_id` (composite FK with organisation), `position`, `kind` (accommodation, extra), `description`, `quantity`, `unit_amount`, `prices_include_tax`, `net_amount`, `tax_amount`, `total_amount`, `taxes` (JSONB), `reservation_room_id`, `service_from`, `service_to` | Trigger `invoice_items_guard`: insert, update and delete only while the invoice is a draft |
| `credit_notes` | `invoice_id`, `number` (UNIQUE per organisation), `reason`, `issue_date`, `currency`, `net_total`, `tax_total`, `total` (> 0), `issued_at`, `issued_by` | INSERT and SELECT only |
| `credit_note_items` | `credit_note_id`, `invoice_item_id`, `description`, amounts, `taxes` (JSONB) | INSERT and SELECT only; total > 0 |

`properties` gained `legal_name` and `tax_number`. Permissions `invoices.view`, `invoices.manage`, `invoices.credit` were added to the catalogue and granted to existing system roles.

## Tables (Phase 3.4)

All use tenant RLS (ADR-0010).

| Table | Key columns | Notes |
|---|---|---|
| `payments` | `property_id`, `reservation_id` (composite FK), `method` (cash, card, bank_transfer, mobile_money, other), `currency`, `amount` (> 0), `received_on`, `payer_name`, `reference`, `note`, `idempotency_key` (UNIQUE per organisation), `recorded_by`, `recorded_at`, `reversed_at`, `reversed_by`, `reversal_reason` | Trigger `payments_guard`: the only allowed update sets the three reversal fields, once. No DELETE |
| `payment_allocations` | `payment_id`, `invoice_id` (composite FKs with organisation), `amount` (non-zero; negative releases), `created_by`, `created_at` | INSERT and SELECT only |
| `refunds` | `payment_id`, `property_id`, `method`, `currency`, `amount` (> 0), `refunded_on`, `reason`, `reference`, `idempotency_key` (UNIQUE per organisation), `recorded_by`, `recorded_at` | INSERT and SELECT only |

## Tables (Phase 3.5)

| Table | Key columns | Notes |
|---|---|---|
| `notifications` | `property_id`, `channel` (email), `kind` (booking_confirmation, invoice, receipt), `subject_type`, `subject_id`, `recipient`, `sender_name`, `reply_to`, `title`, `body_text`, `body_html`, `status` (queued, sent, failed), `attempts`, `next_attempt_at`, `last_error`, `provider`, `provider_message_id`, `idempotency_key` (UNIQUE per organisation), `created_by`, `created_at`, `sent_at` | Tenant RLS plus policy `notifications_worker` for the delivery worker (`app.notification_worker = 'on'`). Partial index on due queued rows. No DELETE |

## Changes (Phase 4.1)

- `properties`: `booking_engine_enabled`, `booking_mode` (request, instant), `public_description`, `booking_terms`, `min_lead_days`, `max_advance_days`, `request_hold_hours`, with CHECKs (terms required when enabled; sensible windows).
- `rate_plans.sell_online`.
- `reservations.hold_expires_at` (partial index on provisional rows with a hold) and `idempotency_key` (UNIQUE per organisation).
- `notifications.created_by` may be empty (system-queued messages).
- Functions `public_booking_property(org_slug, property_slug)` and `expired_request_holds()`: `SECURITY DEFINER`, `search_path` pinned, return ids only, `EXECUTE` granted to `lodgeos_app` only (ADR-0012).

## Changes (Phase 4.2)

- `guest_access_tokens`: `reservation_id` (composite FK with property), `token_hash` (SHA-256, UNIQUE), `created_at`, `expires_at`, `revoked_at`, `created_by` (empty when system-created). Tenant RLS.
- `reservations`: `guest_arrival_time` (CHECK `HH:MM`), `guest_message`, `guest_updated_at`, `cancellation_requested_at`, `cancellation_request_reason`.
- Function `guest_portal_access(hash)`: `SECURITY DEFINER`, returns organisation and reservation ids for a valid, unrevoked, unexpired token only.

## Tables (Phase 4.4)

| Table | Key columns | Notes |
|---|---|---|
| `media_assets` | `property_id`, `room_type_id` (composite FK), `kind` (logo, property_photo, room_type_photo), `alt_text` (required except logos), `sort_order`, `variants` (JSONB: width, height, bytes per size), `storage` (local, s3), `created_by`, `created_at`, `deleted_at` | Tenant RLS; partial index on live assets. Files live in object storage under `{organisation}/{asset}/{size}.webp` |

## Tables (Phase 5.1)

| Table | Key columns | Notes |
|---|---|---|
| `pos_outlets` | `property_id`, `name` (UNIQUE per property), `status` | Tenant RLS |
| `services` | `outlet_id` (composite FK), `name`, `category`, `price` (> 0), `prices_include_tax`, `tax_ids` (JSONB), `sort_order`, `status` | Tenant RLS; archived, never deleted |
| `pos_orders` | `outlet_id`, `settlement` (room, paid), `reservation_id`, `invoice_id`, `payment_id`, `currency`, `total`, `note`, `idempotency_key` (UNIQUE per organisation), `created_by`, `created_at` | INSERT and SELECT only; CHECK: room ⇔ booking, paid ⇔ payment |
| `pos_order_items` | `order_id`, `service_id`, `position`, `name`, `quantity`, `unit_amount`, `total` | INSERT and SELECT only |

## Planned tables

Next (Phase 4): booking-engine sessions, guest portal access tokens, payment-gateway events (`integration_events`).
