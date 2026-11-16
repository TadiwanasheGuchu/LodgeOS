# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project instructions (`CLAUDE.md`), documentation set and architecture decision records 0001–0004.
- Docker Compose development stack: PostgreSQL 17 with separate `lodgeos_owner` (migrations) and `lodgeos_app` (runtime, subject to RLS) roles; Redis 7.
- Backend foundation (FastAPI, SQLAlchemy 2 async, Alembic):
  - Tables `organisations`, `users`, `organisation_users`, `user_sessions`, `audit_logs`, with Row-Level Security on tenant tables.
  - Sign-in with Argon2id, server-side sessions, CSRF protection, login throttling.
  - Organisation switching, role-based permissions, organisation settings, member list, paginated audit log.
  - Health endpoints and `bootstrap-organisation` operator command.
  - Non-root API container image.
- GitHub Actions CI: lint, type check, tests, migration drift check, image build, dependency audit.
