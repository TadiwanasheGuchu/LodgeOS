# Project Status

_Last updated: 2026-11-16_

**Current phase:** 1 — Property management
**Current milestone:** 1.2 complete; next is 1.3 (staff and property-level permissions)

## Phase 1 plan

| Milestone | Scope | Status |
|---|---|---|
| 1.1 | Properties (timezone, currency, address, check-in/out policy) and buildings | ✅ Done |
| 1.2 | Room types and physical rooms; separate housekeeping and maintenance status; room status board | ✅ Done |
| 1.3 | Staff management: invitations, database-backed roles and permissions, property-level access (supersedes ADR-0004) | ⏳ Next |
| 1.4 | Rate plans, seasonal and weekend rates, extra-guest charges, configurable taxes (NUMERIC money) | Not started |

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

## Test results (milestone 1.2)

- Backend: **51 passed, 0 failed**. `ruff`, `mypy --strict`, `alembic check`: clean.
- Frontend unit and component: **10 passed**. ESLint, TypeScript, production build: clean.
- End-to-end: **16 passed, 0 failed** (desktop and phone).
- Bugs found and fixed during the milestone: `Button asChild` crashed pages that used it (regression test added); an orphaned `next-server` process served an outdated build during testing (test procedure now stops it).

## Phase 0

Complete. All acceptance criteria met; CI green on PR #1 (merged). Details in git history and `CHANGELOG.md`.

## Known gaps

See `docs/SECURITY.md` → Known gaps. Main items: no MFA, no staff invitations or password reset (the operator CLI creates accounts), permissions are organisation-wide rather than per property (1.3), no platform-admin role, no offline mode.

## Next

1. Milestone 1.3: staff invitations, roles and permissions in the database, property-level access.
2. Milestone 1.4: rate plans and taxes.
3. Phase 2: availability, reservations, booking calendar, guest records, check-in and check-out.
