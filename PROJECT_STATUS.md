# Project Status

_Last updated: 2026-11-16_

**Current phase:** 2 — Reservations
**Current milestone:** 2.1 complete; next is 2.2 (booking calendar)

## Phase 2 plan

| Milestone | Scope | Status |
|---|---|---|
| 2.1 | Guests, reservation engine (availability, concurrency-safe booking, price snapshot, references, status history), booking form, list, detail, confirm and cancel | ✅ Done |
| 2.2 | Booking calendar (rooms by date), room allocation and moves, arrivals and departures on the overview | ⏳ Next |
| 2.3 | Check-in and check-out (with housekeeping hand-off), booking changes (dates, rooms, guests) through the same inventory lock, no-shows | Not started |

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

1. Phase 2.2: booking calendar and room allocation.
2. Phase 2.3: check-in, check-out and booking changes.
3. Phase 3: availability, reservations, booking calendar, guest records, check-in and check-out.
