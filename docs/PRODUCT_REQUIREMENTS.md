# Product Requirements

The full product brief is `CLAUDE.md`. This document narrows it to what the first sellable release must do, and how we will know.

## Target first customer

An independent guesthouse or lodge in Namibia with roughly 5–40 rooms, one property, a small front-desk team, housekeeping staff on phones, and an owner who wants to see bookings and revenue. Bookings arrive by phone, email, walk-in and WhatsApp today, and possibly through Booking.com.

## MVP scope (Phases 0–3, plus the booking engine from Phase 4)

1. Staff sign in securely; owners control who can do what.
2. Set up the property: room types, physical rooms, rate plans, taxes, currency (NAD by default), timezone (Africa/Windhoek).
3. Take reservations (phone, walk-in, email) against room-type availability, then allocate physical rooms, with no double-booking possible.
4. A booking calendar a receptionist can read at a glance.
5. Guest records with stay history.
6. Check-in and check-out.
7. Housekeeping on a phone: room status updates the front desk sees immediately.
8. Invoices, part payments, refunds and credit notes, with figures that reconcile.
9. A public booking page for direct bookings.

## Out of MVP scope

POS, activities, channel manager and OTA connectivity, advanced analytics, multi-property groups, SaaS billing automation. These follow in Phase 5.

## Success criteria for a pilot

- A receptionist can take a phone booking in under 2 minutes without training notes.
- Zero double allocations of a physical room under concurrent use (enforced by the database and tested).
- End-of-day cash and invoice totals reconcile to the cent.
- Housekeeping status changes appear at the front desk within 5 seconds.
- Usable on a mid-range Android phone over a slow 3G connection for housekeeping and the guest-facing pages.

## Phase 0 acceptance criteria

See `PROJECT_STATUS.md`.
