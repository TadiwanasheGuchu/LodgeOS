# Project Status

_Last updated: 2026-11-23_

**Current phase:** 4 — Booking commerce (4.3 waits on a gateway); 5 — Advanced hospitality started
**Current milestone:** 4.4 complete (photos and logo); 4.3 waits on the payment gateway

## Hosting

Free demo hosting is prepared (ADR-0016, `render.yaml`, `infra/neon/setup.sql`, guide in `docs/DEPLOYMENT.md` → "Free hosting"): Render for the web app and API, Neon for Postgres, Upstash for Redis. Rehearsed locally on a Neon-like database. Needs the product owner's accounts to go live. Not production: no backups, sleeping services, test-mode email.

## Phase 5 plan

| Milestone | Scope | Status |
|---|---|---|
| 5.1 | Point of sale: outlets and items, charge to room (folio) or pay now, idempotent sales | ✅ Done |
| 5.2 | Activities and bookable services (game drives, transfers) with capacity | Planned |
| 5.3 | Reports: occupancy, ADR, RevPAR, revenue by source and outlet | Planned |
| 5.4 | SaaS subscriptions and plan limits | Planned |
| 5.5 | Channel manager connection | Needs a partner agreement |

## Phase 5.1 acceptance criteria

| Criterion | Status |
|---|---|
| Charging to a room needs a checked-in guest and adds lines to one draft folio per booking, with the stay | ✅ Tested |
| Paying now issues an invoice and records and allocates the payment; it appears in the cash-up | ✅ Tested |
| Lines use the property's taxes with the ADR-0007 rule; a retried sale is recorded once | ✅ Tested |
| Items must be active and sold at the chosen outlet; sales cannot be changed in the database | ✅ Tested |
| Front desk sells, only managers change the catalogue; housekeeping has no access; other tenants get 404 | ✅ Tested |
| Tablet till: tap items, basket, room or payment, today's sales | ✅ Tested (E2E) |

Backend **178 passed**; frontend unit **17 passed**; end-to-end **36 passed**.

## Phase 4 plan

| Milestone | Scope | Status |
|---|---|---|
| 4.1 | Public booking engine per property: availability and prices for online rates, request or instant booking, expiring holds, automatic confirmation email, staff settings | ✅ Done |
| 4.2 | Guest portal: secret link per booking (email and WhatsApp), booking, invoices and balance, arrival details, cancellation requests | ✅ Done |
| 4.3 | Payment gateway adapter (provider to be chosen): deposits on the booking engine, webhook idempotency, reconciliation with ADR-0010 payments | Blocked on provider choice |
| 4.4 | Logo, property and room-type photos with S3-compatible storage, shown on the booking page in small sizes for phones | ✅ Done |

## Phase 4.4 acceptance criteria

| Criterion | Status |
|---|---|
| Only real JPEG, PNG or WebP images are accepted, judged by decoding; non-images, GIFs, tiny photos, image bombs and files over 8 MB are refused | ✅ Tested |
| Uploads are re-encoded: phone rotation applied, all metadata (camera, GPS) removed | ✅ Tested (EXIF checked on the served file) |
| Photos stored at 400, 800 and 1600 px WebP (never enlarged); logos at 160 and 480 px with transparency | ✅ Tested |
| The booking page shows logo, hero, more photos and room-type photos with `srcset`, so phones load small files | ✅ Tested (E2E: images load) and screenshot |
| A new logo replaces the old; deleting removes the files; serving accepts only ids and known sizes; local storage refuses paths outside its folder | ✅ Tested |
| S3 adapter stores, reads and deletes through the S3 protocol | ✅ Tested against moto's S3-compatible test server. **Not yet against a real provider** |
| Only property managers upload; other tenants get 404 | ✅ Tested |

## Test results (milestone 4.4)

- Backend: **172 passed, 0 failed** (6 new). Lint, types, migration round trip clean.
- Frontend unit and component: **17 passed**. End-to-end: **35 passed** (extended: owner uploads logo, property and room photos, is asked for a description; the guest's booking page loads them).
- Not yet done: reordering photos by drag and drop (the API accepts `sort_order`), cropping, a real storage provider.

## Phase 4.2 acceptance criteria

| Criterion | Status |
|---|---|
| A link opens exactly one booking; only the token's hash is stored; bad, revoked and expired links are refused alike | ✅ Tested |
| The guest sees dates, rooms, total, issued invoices with paid and balance, contact details and terms, and no staff data | ✅ Tested |
| Arrival time and message reach staff as "From the guest"; a cancellation request is flagged, not applied; staff can keep the booking | ✅ Tested (API and E2E) |
| Cancelled bookings stay visible but cannot be changed | ✅ Tested |
| Confirmation emails (staff and website) carry a working link; staff can share by copy or WhatsApp and withdraw all links | ✅ Tested |
| Works on a phone without horizontal scrolling; private page is not indexed and sends no referrer | ✅ Tested (E2E at 390 px) and screenshot |

## Test results (milestone 4.2)

- Backend: **166 passed, 0 failed** (6 new). Lint, types, migration round trip clean.
- Frontend unit and component: **17 passed**. End-to-end: **34 passed** (new: share a guest link, guest sends arrival details and asks to cancel on a phone, staff see both and keep the booking, withdrawn link stops working).
- Not yet done: paying the balance online from the portal (4.3, gateway), guest-initiated date changes, documents (ID, signed registration card).

## Phase 4.1 acceptance criteria

| Criterion | Status |
|---|---|
| Only enabled, active properties of active organisations are public; slugs must belong together; archiving takes the page offline | ✅ Tested |
| Public requests run under the property's organisation RLS context with no user; only ids cross tenants, through two minimal SECURITY DEFINER functions | ✅ Tested |
| Offers list only rates marked for online sale, rooms free on every night, and parties that fit the room type | ✅ Tested |
| Request mode holds rooms as provisional and cancels unconfirmed requests when the hold expires (rooms freed, reason recorded); confirmed requests never expire | ✅ Tested |
| Instant mode confirms at once | ✅ Tested |
| Abuse controls: rate limits per IP and property, honeypot, terms acceptance, 30-night and window limits, idempotent submits, private rates not bookable by id | ✅ Tested |
| Guest gets a confirmation email; staff see a website booking with the guest's request; internal data never exposed | ✅ Tested |
| Booking page works on a phone without horizontal scrolling | ✅ Tested (E2E at 390 px) and screenshots |

## Test results (milestone 4.1)

- Backend: **160 passed, 0 failed** (6 new). Lint, types, migration round trip clean.
- Frontend unit and component: **17 passed**. End-to-end: **33 passed** (new: owner turns on online booking, terms required, marks a rate for online sale; an anonymous guest books from a phone and gets a reference).
- Not yet done: online payment (4.3), room photos and branding (4.4), multi-room selection in the public UI (the API accepts up to 4 rooms), promo codes, children's ages.

## Phase 3 plan

| Milestone | Scope | Status |
|---|---|---|
| 3.1 | Maintenance tickets (report, assign, work, resolve), dated room blocks that take a room out of sale and count against availability | ✅ Done |
| 3.2 | Housekeeping task lists per day (departures, stay-overs, arrivals), assignment, mobile-first | ✅ Done |
| 3.3 | Invoices from reservations (price snapshot), extras, issuing with gapless numbers, credit notes, printable invoice | ✅ Done |
| 3.4 | Payments, deposits, allocations, refunds, reversals, daily cash-up | ✅ Done |
| 3.5 | Email notifications: outbox, delivery worker, booking confirmations, invoices and receipts, mock and SMTP providers | ✅ Done |

## Phase 3.5 acceptance criteria

| Criterion | Status |
|---|---|
| Booking confirmations, invoices and receipts are rendered from current data and queued in the same transaction as the request | ✅ Tested |
| A repeated request (same idempotency key) queues one message | ✅ Tested |
| The worker delivers due messages, retries failures with backoff and marks them failed after 6 attempts with the last error | ✅ Tested |
| Guest-supplied text is escaped in HTML; internal booking notes are never emailed; no tracking or remote images | ✅ Tested |
| The worker reads every outbox through a dedicated policy; tenant sessions still see only their own messages | ✅ Tested (RLS) |
| The SMTP adapter speaks SMTP correctly (local test server) and turns connection failures into retryable errors | ✅ Tested. **Not yet tested against a commercial provider** (none chosen) |
| The mock provider is clearly labelled "test mode" in the UI and refused in production | ✅ Tested |
| Permissions follow the subject; other tenants get 404 | ✅ Tested |

## Test results (milestone 3.5)

- Backend: **154 passed, 0 failed** (7 new). Lint, types, migration round trip clean.
- Frontend unit and component: **17 passed**. End-to-end: **32 passed** (new: email a confirmation, the API asks for an address when none is on file, the worker delivers it, the log shows "Sent (test mode)").
- Not yet done: choosing a provider and a live delivery check, automatic sending per property, WhatsApp and SMS channels, bounce handling.

## Phase 3.4 acceptance criteria

| Criterion | Status |
|---|---|
| Deposits are taken on a booking before invoicing and applied to the invoice later | ✅ Tested (API and E2E) |
| Paying an invoice allocates up to its balance; the rest stays on account | ✅ Tested |
| Invoice balance = total − credit notes − payments; overpayment after a credit note is released and refunded in one step | ✅ Tested |
| Retried or double-submitted payments and refunds are recorded once (idempotency keys, also under concurrency) | ✅ Tested |
| Two payments cannot over-allocate one invoice (invoice lock; deterministic two-transaction test fails without it) | ✅ Tested |
| Payments are never edited or deleted; reversal is recorded once and releases allocations; refunded payments cannot be reversed | ✅ Tested (API and database) |
| Cash-up shows received, refunded and net per method and day, without reversed payments | ✅ Tested (API and E2E) |
| Front desk records payments; only owners, managers and accountants refund and reverse; other tenants get 404 | ✅ Tested |

## Test results (milestone 3.4)

- Backend: **147 passed, 0 failed** (8 new). Lint, types, migration round trip clean.
- Frontend unit and component: **17 passed**. End-to-end: **31 passed** (new: deposit on a booking → invoice → apply deposit → settle in cash → cash-up shows both methods).
- Not yet done: card gateway payments (Phase 4), multi-currency settlement, bank statement import.

## Phase 3.3 acceptance criteria

| Criterion | Status |
|---|---|
| An invoice for a booking equals the booking exactly (lines copied from the price snapshot: net, each tax, total) | ✅ Tested |
| A booked room can be on only one live invoice; discarding the draft or fully crediting the line frees it | ✅ Tested |
| Extra lines use the ADR-0007 rounding rule with the property's chosen taxes, inclusive or exclusive | ✅ Tested |
| Numbers are gapless per organisation, assigned only on issue; concurrent issues get distinct consecutive numbers | ✅ Tested (fails with the lock removed) |
| Issued invoices cannot be changed through the API or directly in the database (triggers, no DELETE) | ✅ Tested |
| Credit notes split tax by the line's rates, never exceed the remainder, and a full remainder nets every component to zero | ✅ Tested |
| Front desk invoices; only owners, managers and accountants credit; housekeeping sees no invoices; other tenants get 404 | ✅ Tested |
| Printable invoice ("Tax invoice" when the property has a tax number), screen and print layouts checked | ✅ Tested (E2E: book → invoice → extra → issue → credit) |

## Test results (milestone 3.3)

- Backend: **139 passed, 0 failed** (7 new). Lint, types, migration round trip clean.
- Frontend unit and component: **17 passed**. End-to-end: **30 passed** (new: invoice a stay with an extra, issue, credit the extra as owner).
- Not yet done: payments and balances (3.4), emailing invoices (3.5), multi-currency invoices with exchange rates, deposits invoiced before arrival.

## Phase 3.2 acceptance criteria

| Criterion | Status |
|---|---|
| The day's list is worked out from bookings and room status: departures (including early check-outs), stay-overs, arrivals into dirty rooms, vacant dirty rooms | ✅ Tested |
| Departure rooms cannot be started or finished while the guest is still checked in | ✅ Tested |
| Finishing a room marks it clean; reopening sends it back to dirty; stay-overs can be recorded as declined with a reason | ✅ Tested |
| Tomorrow can be planned (assigned) but only today can be worked; past days are read-only | ✅ Tested |
| Only staff who do housekeeping at the property can be assigned; maintenance staff can view but not act; other organisations get 404 | ✅ Tested |
| Housekeeping never sees guest names | ✅ Tested |
| Works on a phone without horizontal scrolling | ✅ Tested (E2E at 390 px) |

## Test results (milestone 3.2)

- Backend: **132 passed, 0 failed** (6 new). Lint, types, migration check clean.
- Frontend unit and component: **17 passed**. End-to-end: **29 passed** (new: housekeeper on a phone starts and finishes the checked-out room; Room status shows it clean).
- Not yet done: inspection workflow inside the list (supervisors use Room status for "Inspected"), linen and minibar counts, offline use.

## Phase 3.1 acceptance criteria

| Criterion | Status |
|---|---|
| Anyone who can see rooms can report a problem for a room or a named area; only maintenance staff can work, assign and close tickets | ✅ Tested (API and E2E) |
| A room block reduces availability on its nights only; blocked rooms cannot be booked or assigned | ✅ Tested |
| A block is refused when guests are in the room or when it would oversell the room type on any night (under the same room-type lock as bookings) | ✅ Tested |
| Resolving or cancelling a ticket releases its blocks; a resolution note is required | ✅ Tested |
| Blocks appear on the booking calendar in the room's row | ✅ Tested (E2E) |
| Ticket and block changes are audited; tenant and property isolation hold | ✅ Tested |

## Test results (milestone 3.1)

- Backend: **126 passed, 0 failed**. Lint, types, migration check (upgrade, downgrade, upgrade) clean.
- Frontend unit and component: **17 passed**. End-to-end: **28 passed** (new: housekeeping reports → maintenance starts and blocks the room → calendar shows the block → marked fixed, ticket moves to Closed).
- Not yet done: photos on tickets (needs secure upload storage), recurring preventive maintenance, notifications to the assignee.

## Phase 2 plan

| Milestone | Scope | Status |
|---|---|---|
| 2.1 | Guests, reservation engine (availability, concurrency-safe booking, price snapshot, references, status history), booking form, list, detail, confirm and cancel | ✅ Done |
| 2.2 | Booking calendar (rooms by date), room allocation and moves, arrivals and departures on the overview | ✅ Done |
| 2.3 | Check-in and check-out (with housekeeping hand-off), date changes through the same inventory lock, no-shows, guest edits | ✅ Done |

## Phase 2.3 acceptance criteria

| Criterion | Status |
|---|---|
| Check-in only for confirmed bookings, from the arrival date in the property's timezone, with every room assigned and usable | ✅ Tested |
| Check-out marks rooms dirty for housekeeping; early departure frees remaining nights | ✅ Tested (API and E2E) |
| No-show only from the arrival date; frees the rooms | ✅ Tested |
| Date changes cannot oversell, do not collide with the booking itself, re-price at current rates, and keep assigned rooms or refuse | ✅ Tested |
| Checked-in bookings cannot be cancelled; every change appears in the history | ✅ Tested |
| Guest edits are audited without personal data in the log | ✅ Tested |

## Test results (milestone 2.3)

- Backend: **120 passed, 0 failed**. Lint, types, migration check clean.
- Frontend unit and component: **17 passed**. End-to-end: **27 passed** (new: arrival today → assign → check in → check out → room shows dirty).
- Not yet done in Phase 2: changing a booking's rooms or room types (cancel and rebook for now), splitting a stay across rooms.

## Phase 2.2 acceptance criteria

| Criterion | Status |
|---|---|
| Only rooms free for every night of a stay are offered; a taken room is refused even if requested directly | ✅ Tested (API and database constraint) |
| Moves stay within the booked room type; out-of-order rooms refused; cancelled bookings cannot be assigned | ✅ Tested |
| Calendar shows active stays only, in their room's row, with unassigned bookings per room type | ✅ Tested (API and E2E) |
| Today's arrivals and departures use the property's own date | ✅ Tested |
| Housekeeping cannot see the calendar; accountants can view but not assign | ✅ Tested |

## Test results (milestone 2.2)

- Backend: **112 passed, 0 failed**. Lint, types, migration check clean.
- Frontend unit and component: **17 passed**. End-to-end: **26 passed**.
- Merged into `main` on 17 November: PRs #3, #4 and #5, each with all CI checks green.

## Phase 2.1 acceptance criteria

| Criterion | Status |
|---|---|
| A room type is never oversold, including under concurrent bookings | ✅ Tested: 8 simultaneous requests → 1 booking; deterministic two-transaction test that fails without the lock |
| A physical room never holds two active stays on one night | ✅ Tested at API and database level (exclusion constraint) |
| Out-of-order rooms are not sold | ✅ Tested |
| Each booking keeps its price when rates change | ✅ Tested |
| Unique reference; status history; cancellation needs a reason and frees inventory | ✅ Tested |
| Bookings and history cannot be deleted | ✅ Tested (no DELETE privilege) |
| Guest details hidden from housekeeping; accountants read-only; other tenants see nothing | ✅ Tested |
| Phone booking and cancellation work end to end | ✅ Tested (E2E) |

## Test results (milestone 2.1)

- Backend: **107 passed, 0 failed**. `ruff`, `mypy --strict`, `alembic check`: clean.
- Frontend unit and component: **17 passed**. ESLint, TypeScript, production build: clean.
- End-to-end: **25 passed, 0 failed**.
- Found and fixed: the first concurrency test passed even with the lock removed, so it proved nothing; replaced with a deterministic two-transaction test, confirmed to fail without the lock. The booking form's preview total first used floating-point arithmetic; now an exact whole-cent sum (`sumMoney`).

## Phase 1 plan

| Milestone | Scope | Status |
|---|---|---|
| 1.1 | Properties (timezone, currency, address, check-in/out policy) and buildings | ✅ Done |
| 1.2 | Room types and physical rooms; separate housekeeping and maintenance status; room status board | ✅ Done |
| 1.3 | Staff management: invitations, database-backed roles and permissions, property-level access (ADR-0006) | ✅ Done |
| 1.4 | Rate plans, seasonal and weekend rates, extra-guest charges, configurable taxes (NUMERIC money; ADR-0007) | ✅ Done |

## Phase 1.1–1.2 acceptance criteria

| Criterion | Status |
|---|---|
| Property timezone and currency default from the organisation and can differ | ✅ Tested |
| Buildings, room types and rooms cannot reference another property (application **and** composite foreign keys) | ✅ Tested, including a direct database insert |
| Other tenants' properties return 404 | ✅ Tested |
| Room numbers unique per property, including under concurrent requests | ✅ Tested (5 simultaneous requests, exactly 1 succeeds) |
| Bulk room creation is all or nothing | ✅ Tested |
| Housekeeping and maintenance status are independent, each with its own permission; maintenance needs a reason | ✅ Tested (API and E2E) |
| Room types with active rooms cannot be archived | ✅ Tested |
| Runtime role cannot delete rooms | ✅ Tested |
| Setup changes and status changes are audit-logged | ✅ Tested |
| Setup flow works end to end; room board usable on a phone without horizontal scroll | ✅ Tested (E2E) and reviewed in screenshots |
| Occupancy and sellability | ⏳ Phase 2 (derived from reservations) |

## Phase 1.4 acceptance criteria

| Criterion | Status |
|---|---|
| Money stored as NUMERIC, sent as decimal strings, never calculated in the browser | ✅ Tested |
| Seasons cannot overlap for one plan and room type (database exclusion constraint) | ✅ Tested (API and E2E) |
| Weekend, seasonal and extra-guest prices applied night by night | ✅ Tested |
| Taxes configured per property; nothing country-specific in code | ✅ |
| Net + taxes = total exactly; each tax matches its rate | ✅ Tested over 4,000 randomised cases plus a regression test |
| Stays that cannot be priced are explained (occupancy, minimum stay, validity, missing price) | ✅ Tested |
| Receptionists can price stays but not change rates; other tenants see nothing | ✅ Tested |

## Phase 1.3 acceptance criteria

| Criterion | Status |
|---|---|
| Existing members keep exactly their access through the migration; downgrade restores it | ✅ Verified on the development database (51 memberships) |
| Roles can be granted for all properties or one; scoped staff see only their properties | ✅ Tested (API and E2E) |
| No one can grant, remove or disable beyond their own permissions | ✅ Tested |
| The last active owner is protected; nobody changes their own access | ✅ Tested |
| Revoking a role takes effect on the next request | ✅ Tested |
| Invitations: single use, expire, can be withdrawn, re-inviting replaces the link, tokens hashed | ✅ Tested |
| Existing accounts must prove ownership to accept | ✅ Tested |
| Roles, memberships and assignments from other organisations are never listed or usable | ✅ Tested (two regression tests) |
| Invitation flow works end to end in a fresh browser | ✅ Tested (E2E) |

## Test results (milestone 1.4)

- Backend: **94 passed, 0 failed**. `ruff`, `mypy --strict`, `alembic check`: clean.
- Frontend unit and component: **14 passed**. ESLint, TypeScript, production build: clean.
- End-to-end: **22 passed, 0 failed**.
- Bugs found and fixed: the price calculator kept a stale plan selection after a plan was added; tax rounding put the cent on the last tax (VAT one cent off its rate, found by checking a screenshot by hand); repeated local E2E runs hit the sign-in throttle (the setup now clears only those counters).

## Test results (milestone 1.3)

- Backend: **66 passed, 0 failed**. `ruff`, `mypy --strict`, `alembic check`: clean.
- Frontend unit and component: **11 passed**. ESLint, TypeScript, production build: clean.
- End-to-end: **20 passed, 0 failed**.
- Bugs found and fixed: the new RLS policy made a user's roles in other organisations visible, so `/roles` listed a second "Owner" and own memberships elsewhere could reach member endpoints (writes were still blocked by RLS); the CLI did not register all models; a scoped receptionist initially lost `organisation.view`; a lint failure was committed and fixed in the next commit.

## Test results (milestone 1.2)

- Backend: **51 passed, 0 failed**. `ruff`, `mypy --strict`, `alembic check`: clean.
- Frontend unit and component: **10 passed**. ESLint, TypeScript, production build: clean.
- End-to-end: **16 passed, 0 failed** (desktop and phone).
- Bugs found and fixed during the milestone: `Button asChild` crashed pages that used it (regression test added); an orphaned `next-server` process served an outdated build during testing (test procedure now stops it).

## Phase 0

Complete. All acceptance criteria met; CI green on PR #1 (merged). Details in git history and `CHANGELOG.md`.

## Known gaps

See `docs/SECURITY.md` → Known gaps. Main items: no MFA, no password reset, no email delivery (invitation links are shared by hand), property scope enforced in the application rather than RLS, no platform-admin role, no offline mode.

## Next

1. Milestone 4.3 once DPO Pay (recommended) or another gateway provides test credentials. Otherwise Phase 5 (POS, activities, reporting) can start.
2. Decisions needed from the product owner: email provider (any with SMTP), payment gateway for Namibia/Zimbabwe, and whether invoice numbering should be per property (separate legal entities) or per organisation (current).
