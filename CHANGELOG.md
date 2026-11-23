# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed
- Security: a form sent before the page's scripts had loaded (likely on slow connections) was submitted by the browser as a GET, putting the sign-in email and password, or other form fields, in the URL and so in browser history and server logs. Every form now falls back to POST; an end-to-end test covers sign-in with scripts disabled.

### Changed
- End-to-end tests in CI: no automatic retries (the ordered specs share data, so a retry re-created records and hid the first failure); screenshots and error context of failed tests are kept as a CI artifact; the API's request log is shown in the CI output.

### Added
- Photos and logo (ADR-0014): a Photos tab on each property for the logo, property photos and room-type photos (with required descriptions); images are checked by decoding, re-encoded without metadata and stored as small WebP sizes in local or S3-compatible storage; the booking page shows the logo, a hero photo, more photos and room photos sized for phones.
- Guest portal (ADR-0013): a private link per booking (in confirmation emails, or shared by staff by copy or WhatsApp) where guests see their booking, invoices and balance, send arrival time and a message, and ask to cancel. Staff see "From the guest" and a cancellation-request banner, and can withdraw links. Only token hashes are stored.
- Public booking engine (ADR-0012): a booking page per property (`/book/{organisation}/{property}`), built for phones, with availability and prices for rates marked "sell online", request or instant booking, holds that expire, automatic confirmation email, rate limits and a honeypot. Staff "Online booking" tab: go live, terms, description, booking window, hold time and which rates are sold online. The worker (`run-worker`) now also expires holds.
- Email notifications (ADR-0011): "Email confirmation" on bookings, "Email invoice" on issued invoices and "Email receipt" on payments, queued in an outbox and delivered by a worker (`deliver-notifications`, `worker` Compose service) with retries. Mock provider by default (clearly labelled test mode), standard SMTP adapter for any provider. Sent-email history with delivery status on each booking and invoice.
- Payments (ADR-0010): deposits on bookings, payments against invoices (allocated up to the balance, rest on account), applying deposits to invoices, refunds (including releasing an overpayment after a credit note), reversal of payments recorded in error, balance due on invoices, a payments panel on each booking, and a daily cash-up page by method. Idempotency keys prevent double recording; payments, allocations and refunds are protected by database triggers and privileges. New permissions `payments.view`, `payments.manage`, `payments.refund`.
- Invoices (ADR-0009): create from a booking (lines equal to the booking's price), invoices without a booking, extra lines with the property's taxes, draft editing, issuing with gapless numbers per organisation, discarding drafts, credit notes per line with exact tax splits, printable invoice ("Tax invoice" with a tax number), invoice list, and an Invoices panel on each booking. Issued invoices and credit notes are protected by database triggers and privileges. New permissions `invoices.view`, `invoices.manage`, `invoices.credit`; property legal name and tax number.
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
