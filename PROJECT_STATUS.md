# Project Status

_Last updated: 2026-11-16_

**Current phase:** 1 — Property management
**Current milestone:** 1.3 complete; next is 1.4 (rate plans and taxes)

## Phase 1 plan

| Milestone | Scope | Status |
|---|---|---|
| 1.1 | Properties (timezone, currency, address, check-in/out policy) and buildings | ✅ Done |
| 1.2 | Room types and physical rooms; separate housekeeping and maintenance status; room status board | ✅ Done |
| 1.3 | Staff management: invitations, database-backed roles and permissions, property-level access (ADR-0006) | ✅ Done |
| 1.4 | Rate plans, seasonal and weekend rates, extra-guest charges, configurable taxes (NUMERIC money) | ⏳ Next |

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

1. Milestone 1.4: rate plans, seasonal and weekend rates, extra-guest charges, taxes.
2. Phase 2: availability, reservations, booking calendar, guest records, check-in and check-out.
