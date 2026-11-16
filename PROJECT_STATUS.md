# Project Status

_Last updated: 2026-11-16_

**Current phase:** 0 — Foundation
**Current milestone:** Phase 0 complete; Phase 1 (property management) in progress

## Phase 0 plan

| Milestone | Scope | Status |
|---|---|---|
| 0.1 | Repository, architecture docs, ADRs, Docker Compose (Postgres, Redis) | ✅ Done |
| 0.2 | Backend foundation: config, DB roles, migrations, RLS, authentication, sessions, CSRF, throttling, organisations, memberships, RBAC map, audit log, health checks, CLI, API image | ✅ Done |
| 0.3 | Frontend foundation: Next.js app, design tokens, fonts, sign-in, organisation picker, role-aware app shell, organisation settings, team list, activity log, nonce CSP, unit/component/E2E tests | ✅ Done |
| 0.4 | First green CI run on GitHub; installable PWA manifest and icons; warning status colour | ✅ Done |

## Phase 0 acceptance criteria

| Criterion | Status |
|---|---|
| `docker compose up` starts Postgres and Redis with separate owner and runtime roles | ✅ Verified |
| Migrations upgrade, downgrade and re-upgrade cleanly; models and migrations match (`alembic check`) | ✅ Tested |
| Staff sign in with Argon2id-hashed passwords; sessions expire (idle and absolute) and revoke on logout | ✅ Tested |
| State-changing requests require a CSRF token | ✅ Tested |
| Sign-in is throttled and fails closed without Redis | ✅ Tested |
| A user in several organisations chooses one; cannot switch into one they don't belong to | ✅ Tested (API and E2E) |
| Tenant data is isolated by the API **and** by RLS, proven with direct database tests | ✅ Tested |
| Runtime role cannot delete data or alter audit logs | ✅ Tested |
| Permissions enforced per role, in the API and in what the UI shows | ✅ Tested (API and E2E) |
| Changes and sign-ins are audit-logged and visible to permitted roles | ✅ Tested (API and E2E) |
| API container builds and runs as non-root | ✅ Verified manually |
| Design tokens implemented, contrast measured | ✅ Done (`docs/DESIGN_SYSTEM.md`) |
| Sign-in screen and app shell, usable on a phone without horizontal scroll | ✅ Tested (E2E on Pixel 7 viewport) |
| Pages served with a strict nonce CSP and no console errors | ✅ Tested (E2E) |
| CI green on GitHub | ✅ All 5 jobs passed on PR #1 (merged) |
| Installable PWA | ✅ Manifest and icons served (E2E); no offline mode yet |

## Test results (milestone 0.3)

- Backend: **35 passed, 0 failed** (`uv run pytest`; real PostgreSQL 17 and Redis 7). `ruff`, `mypy --strict`: clean. `pip-audit`: no known vulnerabilities.
- Frontend unit and component tests: **5 passed** (`npm test`). ESLint and TypeScript: clean. Production build: succeeds.
- End-to-end: **11 passed, 0 failed** (`npm run e2e`; Chromium desktop and Pixel 7 against the real API and database).
- `npm audit --omit=dev`: 0 vulnerabilities. Full audit: 8 moderate findings in ESLint's tooling (development only; see `docs/SECURITY.md`).
- Manual review of screenshots: sign-in, overview, settings, activity log, team, phone menu.

## Repository state

- History on `main` carries no AI attribution. Branch `phase-0-foundation-clean` is obsolete and can be deleted (the session's git proxy refused the deletion).

## Known gaps

See `docs/SECURITY.md` → Known gaps. Main items: no MFA, no staff invitations or password reset (the operator CLI creates accounts), no platform-admin role, no offline mode.

## Next

1. Milestone 0.4: open a pull request so CI runs; fix anything it finds; PWA manifest and icons; warning colour.
2. Phase 1: properties and buildings, room types and physical rooms, staff management with database-backed roles and property-level permissions (supersedes ADR-0004), rate plans.
