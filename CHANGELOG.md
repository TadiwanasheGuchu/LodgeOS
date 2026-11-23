# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Housekeeping day list (`/housekeeping`), built for phones: what each room needs today (departure clean, stay-over, arrival, vacant dirty) worked out from bookings, turnovers first, start and done (marks the room clean), service declined with a reason, reopen, "only my rooms", and assigning rooms for tomorrow. Departures can't be cleaned until the guest has checked out; early check-outs appear on the day the guest left. Guest names are never shown.
- Maintenance: report a problem for a room or an area (anyone who sees rooms), urgent-first ticket list, start work, assign, resolve with a note, closed-ticket history. Rooms can be taken out of sale for specific dates; the block counts against availability, is refused if guests are in the room or it would oversell, shows on the booking calendar, and is released when the ticket is fixed.
- Check-in (needs an assigned room, from the arrival date), check-out (room handed to housekeeping as dirty), no-shows, and changing a booking's dates with availability re-checked and the stay re-priced. Guest details can be corrected.
- Booking calendar: rooms by date with stays as bars, bookings without a room shown per room type, weekend nights shaded.
- Assigning, moving and removing a booking's physical room, offering only rooms free for every night.
- Today's arrivals and departures on the overview for front-desk roles.
- Reservations: availability per night, bookings by phone, walk-in or other sources with one or more rooms, returning-guest search, provisional and confirmed bookings, cancellation with a required reason, status history, and the price frozen at booking. No overbooking and no double-booked rooms, enforced in the database (ADR-0008).
- Rates: taxes per property, rate plans (standard, corporate, promotion, package; meal plan; minimum stay; validity window), prices per room type with weekend and extra-guest prices, non-overlapping seasons, configurable weekend nights, and a price calculator that shows every night, each tax and the total (ADR-0007).
- Staff management: roles and permissions in the database, roles for all properties or one property, invitations by shareable link (copy or WhatsApp), turning access off and on. Team page rewritten for this.
- Property-scoped access throughout the API and UI; properties without access are not found.
- Properties with their own timezone, currency, address and check-in/check-out times; buildings; room types with occupancy limits; physical rooms. Archive instead of delete.
- Database-level integrity: composite foreign keys keep buildings, room types and rooms within one property and one organisation; RLS on all four tables.
- Room status board (`/rooms`): one-tap Dirty / Clean / Inspected for housekeeping, and out-of-service / out-of-order with a required reason for maintenance, each behind its own permission.
- Property setup screens: details, room types, rooms (bulk add with ranges such as `101-110, A1-A4`), buildings.
- Installable web app: manifest, app icons ("L." mark in Fraunces) and a maskable icon.
- Warning colour tokens and a warning alert style.
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
