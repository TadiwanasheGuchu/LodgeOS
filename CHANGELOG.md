# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Frontend (Next.js 16, React 19, Tailwind 4): Forest & Teal design tokens with measured contrast, Fraunces / DM Sans / IBM Plex Mono, sign-in, organisation picker, role-aware app shell (sidebar on desktop, menu on phones), overview, organisation settings (editable by owners, read-only for others), team list, activity log with pagination.
- Nonce-based Content-Security-Policy and security headers on every page.
- Frontend tests: Vitest unit and component tests; Playwright end-to-end tests against the real API, including a phone viewport.
- `add-member` operator command; audit log entries now include the actor's name.
- CI jobs for the frontend (lint, types, tests, build, production dependency audit) and end-to-end tests.
- ADR-0005 (same-origin frontend, per-request rendering).
- Project instructions (`CLAUDE.md`), documentation set and architecture decision records 0001–0004.
- Docker Compose development stack: PostgreSQL 17 with separate `lodgeos_owner` (migrations) and `lodgeos_app` (runtime, subject to RLS) roles; Redis 7.
- Backend foundation (FastAPI, SQLAlchemy 2 async, Alembic):
  - Tables `organisations`, `users`, `organisation_users`, `user_sessions`, `audit_logs`, with Row-Level Security on tenant tables.
  - Sign-in with Argon2id, server-side sessions, CSRF protection, login throttling.
  - Organisation switching, role-based permissions, organisation settings, member list, paginated audit log.
  - Health endpoints and `bootstrap-organisation` operator command.
  - Non-root API container image.
- GitHub Actions CI: lint, type check, tests, migration drift check, image build, dependency audit.

### Changed
- Commit messages carry no AI attribution (`CLAUDE.md` §16).
