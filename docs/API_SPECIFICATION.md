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

## Endpoints (Phase 1.3)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/roles` | `members.view` | Roles of the active organisation with their permissions |
| GET | `/api/v1/organisation/members` | `members.view` | Members with `role_label`, `status` and `assignments` (role and property) |
| POST | `/api/v1/members/{id}/roles` | `members.manage` | `{role_id, property_id?}`; 403 beyond your own permissions; 409 if already held; owner cannot be limited to a property |
| DELETE | `/api/v1/members/{id}/roles/{assignment_id}` | `members.manage` | 409 if it would leave no active owner |
| PATCH | `/api/v1/members/{id}` | `members.manage` | `{status: active\|disabled}`; not yourself; not someone holding more than you |
| GET / POST | `/api/v1/invitations` | view / manage | Create returns `token` once; a new invitation replaces a pending one for the same email |
| POST | `/api/v1/invitations/{id}/revoke` | `members.manage` | |
| GET | `/api/v1/invitations/token/{token}` | public, rate limited | Preview: organisation, role, property, whether the email already has an account. 404 unknown, 410 used/withdrawn/expired |
| POST | `/api/v1/invitations/accept` | public, CSRF, rate limited | `{token, password, full_name?}`; existing accounts must give their own password; signs the person in |

`GET /api/v1/auth/me` now returns `active_organisation.role_label`, `permissions` (granted for every property) and `property_permissions` (`{property_id: [...]}`); memberships carry `role_label`.

## Endpoints (Phase 1.4)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET / POST | `/api/v1/properties/{id}/taxes` | `rates.view` / `rates.manage` | |
| PATCH | `/api/v1/taxes/{id}` | `rates.manage` | Name, rate, order, `status: archived` to stop charging |
| GET / POST | `/api/v1/properties/{id}/rate-plans` | view / manage | Create copies the property's currency |
| GET / PATCH | `/api/v1/rate-plans/{id}` | view / manage | Detail includes `prices` and `seasons` |
| PUT / DELETE | `/api/v1/rate-plans/{id}/prices/{room_type_id}` | `rates.manage` | Set or clear the normal prices for a room type |
| POST | `/api/v1/rate-plans/{id}/seasons` | `rates.manage` | 409 if it overlaps another season for that room type |
| PATCH / DELETE | `/api/v1/seasons/{id}` | `rates.manage` | |
| POST | `/api/v1/properties/{id}/quote` | `rates.view` | `{rate_plan_id, room_type_id, check_in, check_out, adults, children}` → nights, net, taxes, total. 422 with a plain explanation when the stay cannot be priced |

All amounts are decimal strings, e.g. `"1250.00"`.

## Endpoints (Phase 2.1)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/guests?q=` | `reservations.view` | Search by name, email or phone (20 results) |
| GET | `/api/v1/properties/{id}/availability?check_in&check_out` | `reservations.view` | Per room type: free rooms per night and for the whole stay |
| GET | `/api/v1/properties/{id}/reservations?from&to` | `reservations.view` | Stays overlapping the range (max 120 days); `include_cancelled` |
| POST | `/api/v1/properties/{id}/reservations` | `reservations.manage` | `{check_in, check_out, guest_id \| guest, rooms[{room_type_id, rate_plan_id, adults, children, room_id?}], status, source, notes}`. 409 when not enough rooms are free (message names the night) or a chosen room is taken; 422 when a room cannot be priced |
| GET | `/api/v1/reservations/{id}` | `reservations.view` | Guest, rooms with price snapshots, status history |
| POST | `/api/v1/reservations/{id}/confirm` | `reservations.manage` | Provisional → confirmed |
| POST | `/api/v1/reservations/{id}/cancel` | `reservations.manage` | `{reason}` required |

## Endpoints (Phase 2.2)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/reservation-rooms/{id}/free-rooms` | `reservations.view` | Rooms of the booked type with no overlapping active stay, not out of order |
| POST | `/api/v1/reservation-rooms/{id}/assign` | `reservations.manage` | `{room_id \| null}`: assign, move within the room type, or unassign. 409 if the room is taken (exclusion constraint) or out of order |
| GET | `/api/v1/properties/{id}/calendar?start&days` | `reservations.view` | Rooms and active stays for up to 31 days |
| GET | `/api/v1/properties/{id}/today` | `reservations.view` | Arrivals, departures, in-house count and unassigned arrivals for today in the property's timezone |

## Endpoints (Phase 2.3)

| Method | Path | Permission | Description |
|---|---|---|---|
| POST | `/api/v1/reservations/{id}/check-in` | `reservations.manage` | Confirmed bookings, from the arrival date (property timezone) and before departure; every booked room needs an assigned room that is not out of order |
| POST | `/api/v1/reservations/{id}/check-out` | `reservations.manage` | From checked in; marks each room dirty for housekeeping; an early departure frees the remaining nights |
| POST | `/api/v1/reservations/{id}/no-show` | `reservations.manage` | Provisional or confirmed, from the arrival date; frees the rooms |
| PATCH | `/api/v1/reservations/{id}/dates` | `reservations.manage` | `{check_in, check_out}` for provisional or confirmed bookings; same lock-and-count as a new booking (not counting its own rooms); re-priced at current rates; assigned rooms kept or 409 |
| PATCH | `/api/v1/guests/{id}` | `reservations.manage` | Correct name and contact details; the audit log records field names only |

Status flow: provisional → confirmed → checked in → checked out; provisional or confirmed → cancelled (reason) or no-show.

## Endpoints (Phase 3.1)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/properties/{id}/maintenance/tickets?closed` | `rooms.view` | Open tickets (urgent first, then oldest), or closed ones with `closed=true`; each with its room blocks |
| POST | `/api/v1/properties/{id}/maintenance/tickets` | `rooms.view` | Report a problem: `{room_id \| location, title, description, priority}` |
| PATCH | `/api/v1/maintenance/tickets/{id}` | `rooms.maintenance_update` | Status, priority, assignee (active member), resolution. Resolving needs a resolution; closing releases the ticket's blocks. 409 once closed |
| POST | `/api/v1/maintenance/tickets/{id}/blocks` | `rooms.maintenance_update` | `{start_date, end_date}` (end exclusive). 409 if guests are in the room, it overlaps another block, or it would oversell the room type |
| POST | `/api/v1/room-blocks/{id}/release` | `rooms.maintenance_update` | Put the room back on sale |
| GET | `/api/v1/properties/{id}/room-blocks?from&to` | `rooms.view` | Active blocks overlapping the range (calendar) |

## Endpoints (Phase 3.2)

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/properties/{id}/housekeeping?date` | `rooms.view` | Every active room with what it needs that day (`departure`, `stayover`, `arrival`, `vacant` or null), whether a guest is leaving, has left, is staying or arriving, the head count (no names), the day's task, and who can be assigned. Defaults to today in the property's timezone |
| POST | `/api/v1/properties/{id}/housekeeping/{date}/rooms/{room_id}` | `rooms.housekeeping_update` | `{action: assign\|start\|done\|decline\|reopen, assigned_to?, note?}`. Assign for today or later; other actions today only. `done` marks a dirty room clean; `reopen` marks it dirty; `decline` only for stay-overs, with a note. 409 while a departing guest is still checked in. Returns the updated day |

## Endpoints (Phase 3.3)

Invoices and credit notes follow ADR-0009. Amounts are decimal strings.

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/v1/properties/{id}/invoices?status&reservation_id&limit&offset` | `invoices.view` | Issued and draft invoices (discarded only with `status=discarded`), with credited totals |
| POST | `/api/v1/properties/{id}/invoices` | `invoices.manage` | Draft: `{reservation_id?, bill_to_name?, bill_to_details?, notes?}`. With a booking, its rooms not already on a live invoice become lines copied from the price snapshot; bill-to defaults to the guest. 409 when every room is already invoiced |
| GET | `/api/v1/invoices/{id}` | `invoices.view` | Invoice with seller details, lines (with credited amounts), tax summary and credit notes |
| PATCH | `/api/v1/invoices/{id}` | `invoices.manage` | Drafts only: bill-to, notes, due date. 409 once issued |
| POST | `/api/v1/invoices/{id}/items` | `invoices.manage` | Drafts only: extra line `{description, quantity, unit_amount, prices_include_tax, tax_ids}` computed with the ADR-0007 rule |
| DELETE | `/api/v1/invoices/{id}/items/{item_id}` | `invoices.manage` | Drafts only |
| POST | `/api/v1/invoices/{id}/reservation-rooms?reservation_id` | `invoices.manage` | Drafts only: add another booking's uninvoiced rooms (same currency) |
| POST | `/api/v1/invoices/{id}/issue` | `invoices.manage` | Assigns the next gapless number and the issue date (property timezone); the invoice is then immutable |
| POST | `/api/v1/invoices/{id}/discard` | `invoices.manage` | Drafts only; kept for the record, frees its booked rooms |
| POST | `/api/v1/invoices/{id}/credit-notes` | `invoices.credit` | `{reason, lines: [{invoice_item_id, amount?}]}` on an issued invoice; no amount credits the line's remainder exactly. 422 above the remainder |

`PATCH /api/v1/properties/{id}` also accepts `legal_name` and `tax_number`, printed on invoices.

## Endpoints (Phase 3.4)

Payments follow ADR-0010. `idempotency_key` (8–64 characters, letters, digits, `-`, `_`) is generated by the client per attempt; repeating it returns the original record (200) instead of creating another (201).

| Method | Path | Permission | Description |
|---|---|---|---|
| POST | `/api/v1/properties/{id}/payments` | `payments.manage` | `{method, amount, received_on?, payer_name?, reference?, note?, reservation_id?, invoice_id?, idempotency_key}`. With `invoice_id`, allocates up to the balance; the rest stays on account. Payer defaults to the invoice's bill-to or the booking's guest. No future dates |
| GET | `/api/v1/payments/{id}` | `payments.view` | Payment with allocations, refunds, allocated / refunded / unallocated |
| POST | `/api/v1/payments/{id}/allocations` | `payments.manage` | `{invoice_id, amount}`: up to the payment's unallocated amount and the invoice's balance; same property and currency; issued invoices only |
| POST | `/api/v1/payments/{id}/release` | `payments.manage` | `{invoice_id, amount}`: writes a negative allocation |
| POST | `/api/v1/payments/{id}/refunds` | `payments.refund` | `{amount, method, reason, reference?, release_from_invoice_id?, idempotency_key}`. Refunds unallocated money; with `release_from_invoice_id`, first releases up to the invoice's overpayment |
| POST | `/api/v1/payments/{id}/reverse` | `payments.refund` | `{reason}`: for payments recorded in error; releases its allocations; refused once refunded |
| GET | `/api/v1/invoices/{id}/payments` | `payments.view` | Total, credited, paid, balance (negative when overpaid) and the payments |
| GET | `/api/v1/properties/{id}/payments?reservation_id&unallocated_only` | `payments.view` | Recent payments |
| GET | `/api/v1/properties/{id}/cash-up?from&to` | `payments.view` | Received, refunded and net per method and currency, per day and in total (up to 93 days; reversed payments excluded), plus the payments and refunds |

## Role permissions

Defaults of the six system roles (organisation-wide grants). A role granted for one property applies its `properties.*`, `rooms.*`, `rates.*`, `reservations.*`, `invoices.*` and `payments.*` permissions to that property only.

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
| rates.view | ✓ | ✓ | ✓ | | | ✓ |
| rates.manage | ✓ | ✓ | | | | |
| reservations.view | ✓ | ✓ | ✓ | | | ✓ |
| reservations.manage | ✓ | ✓ | ✓ | | | |
| invoices.view | ✓ | ✓ | ✓ | | | ✓ |
| invoices.manage | ✓ | ✓ | ✓ | | | ✓ |
| invoices.credit | ✓ | ✓ | | | | ✓ |
| payments.view | ✓ | ✓ | ✓ | | | ✓ |
| payments.manage | ✓ | ✓ | ✓ | | | ✓ |
| payments.refund | ✓ | ✓ | | | | ✓ |
