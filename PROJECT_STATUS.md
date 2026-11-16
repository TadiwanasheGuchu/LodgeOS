# Project Status

_Last updated: 2026-11-16_

**Current phase:** 0 — Foundation
**Current milestone:** 0.2 complete; next is 0.3 (frontend foundation)

## Phase 0 plan

| Milestone | Scope | Status |
|---|---|---|
| 0.1 | Repository, architecture docs, ADRs, Docker Compose (Postgres, Redis) | ✅ Done |
| 0.2 | Backend foundation: config, DB roles, migrations, RLS, authentication, sessions, CSRF, throttling, organisations, memberships, RBAC map, audit log, health checks, CLI, API image | ✅ Done |
| 0.3 | Frontend foundation: Next.js app, design tokens, fonts, sign-in, organisation picker, app shell per role, CSP | ⏳ Next |
| 0.4 | CI hardening: frontend lint/type/test, Playwright smoke test of sign-in, image build on PR | Not started |

CI for the backend (lint, types, tests, migration drift, image build, dependency audit) is defined in `.github/workflows/ci.yml` and was verified locally step by step. **It has not yet run on GitHub**; confirm the first run after push.

## Phase 0 acceptance criteria

| Criterion | Status |
|---|---|
| `docker compose up` starts Postgres and Redis with separate owner and runtime roles | ✅ Verified |
| Migrations upgrade, downgrade and re-upgrade cleanly; models and migrations match (`alembic check`) | ✅ Tested |
| Staff sign in with Argon2id-hashed passwords; sessions expire (idle and absolute) and revoke on logout | ✅ Tested |
| State-changing requests require a CSRF token | ✅ Tested |
| Sign-in is throttled and fails closed without Redis | ✅ Tested |
| A user in several organisations chooses one; cannot switch into one they don't belong to | ✅ Tested |
| Tenant data is isolated by the API **and** by RLS, proven with direct database tests | ✅ Tested |
| Runtime role cannot delete data or alter audit logs | ✅ Tested |
| Permissions enforced per role | ✅ Tested (organisation endpoints) |
| Changes and sign-ins are audit-logged | ✅ Tested |
| API container builds and runs as non-root | ✅ Verified manually |
| Design tokens implemented in the frontend | ⏳ Milestone 0.3 |
| Sign-in screen and app shell | ⏳ Milestone 0.3 |
| CI green on GitHub | ⏳ Pending first run |

## Test results (milestone 0.2)

- Backend: **33 passed, 0 failed** (`uv run pytest`, real PostgreSQL 17 and Redis 7).
- `ruff check`, `ruff format --check`, `mypy --strict`: clean.
- `pip-audit`: no known vulnerabilities.
- Live check: bootstrapped an organisation with the CLI, signed in through the running API, changed settings, read the audit trail.

## Known gaps

See `docs/SECURITY.md` → Known gaps. Main items: no MFA, no invitations or password reset (accounts come from the CLI), no platform-admin role, no frontend yet.

## Next milestone (0.3)

Next.js app in `frontend/` with Forest & Teal tokens (contrast-checked, see `docs/DESIGN_SYSTEM.md`), Fraunces / DM Sans / IBM Plex Mono, sign-in, organisation picker, and a role-aware app shell. Then Phase 1: properties, buildings, room types, rooms, staff management and rate plans.
