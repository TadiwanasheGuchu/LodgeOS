# 0012 — Public booking engine

**Status:** Accepted, 2026-11-23

## Context
Each property needs a public page where guests check availability and book directly, without an account. It is the first unauthenticated path that writes tenant data. It must not weaken tenant isolation, must not let anyone fill a small lodge's inventory with fake bookings, and must work on slow mobile connections. No payment gateway is chosen yet, so online payment comes later; the engine must be useful without it.

## Decision
- **Opt-in per property.** Properties gain `booking_engine_enabled` (off by default), `booking_mode`, public description, booking terms (required before enabling), the earliest and latest bookable dates (`min_lead_days`, `max_advance_days`) and `request_hold_hours`. Only rate plans marked `sell_online` are offered; corporate and other private plans never are.
- **Two modes.**
  - `request` (default): the booking is **provisional** and holds the rooms until staff confirm it, or until `hold_expires_at` (`request_hold_hours` after booking), when the worker cancels it with a reason and frees the rooms.
  - `instant`: the booking is **confirmed** at once, to be paid at the property until online payment exists.
- **Tenant context without a user.** A `SECURITY DEFINER` function `public_booking_property(org_slug, property_slug)` returns the organisation and property ids only for an active property with the engine enabled in an active organisation. The request then sets that organisation as its RLS context (no user) and uses the ordinary services and RLS. Every public query is also filtered by that property. Nothing else is reachable: other organisations are hidden by RLS, and other properties by the filter.
- **Same booking rules as staff.** Public bookings go through `create_reservation`: room-type lock, per-night availability, maintenance blocks, price snapshot. Source is `website`, `created_by` is empty, and the audit entry records `via: website`.
- **Abuse limits.**
  - Rate limits per IP: 60 searches per minute and 5 bookings per hour. Each property also accepts at most 30 public bookings per hour.
  - A hidden honeypot field.
  - At most 4 rooms and 30 nights per booking.
  - The guest must accept the terms and give an email address.
  - Request-mode holds expire. Idempotency keys stop double submissions.
- **Guest privacy.** Public responses contain no other guest's data and no internal notes. A public booking always creates a new guest record and is never matched to an existing guest by email, so knowing an email address reveals nothing. A guest's special requests are stored in the booking notes under a "Guest request:" prefix so staff see them.
- **Confirmation email** is queued automatically for public bookings (the guest asked for it), through the ADR-0011 outbox.
- **Expiring holds:** a second `SECURITY DEFINER` function `expired_request_holds()` lists only the ids of provisional bookings whose hold has passed. For each one, the worker sets that organisation's context and cancels it through the normal status change, so history and audit are complete.

## Consequences
- A property can take direct bookings without any payment integration; card payment (Phase 4.3) will slot into instant mode as a deposit step.
- The two `SECURITY DEFINER` functions are the only tenant-crossing reads in the application and must stay minimal. Tests cover disabled, archived and unknown properties.
- Room photos and property branding (logo, colours within the palette) need file storage and are a later milestone.
