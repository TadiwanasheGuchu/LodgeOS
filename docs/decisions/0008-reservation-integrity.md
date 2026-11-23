# 0008 — Reservation integrity under concurrency

**Status:** Accepted, 2026-11-17

## Context
Two receptionists, an online booking and an OTA can try to sell the last room at the same moment. Overbooking a small lodge is a serious failure; so is changing the price of a confirmed booking because rates were edited later.

## Decision
- **Physical rooms:** `reservation_rooms` has an exclusion constraint on `(room_id, daterange(check_in, check_out, '[)'))` for active statuses (provisional, confirmed, checked in). Two active stays can never share a room-night, whatever the application does. Departure day and the next arrival day may coincide.
- **Room-type inventory:** booking locks the needed `room_types` rows with `SELECT ... FOR UPDATE` in id order (no deadlocks), then counts free rooms per night inside the same transaction. Concurrent bookings for a room type run one after another. Sellable rooms are active rooms that are not out of order.
- **Proof:** a test runs two real transactions: A books the last room and stays open; B must wait and then be refused. With the lock removed, the test fails (checked by hand).
- **Price snapshot:** each booked room stores the quote breakdown (nights, net, taxes, total) as JSON plus NUMERIC totals. Later rate changes never alter a booking.
- **No deletion:** reservations, rooms and status history are never deleted (no DELETE privilege). Cancellation is a status with a required reason; every status change is appended to `reservation_status_history`.
- **References:** `LOS-` plus six characters from an alphabet without 0/O and 1/I, unique per organisation.

## Consequences
- Bookings for one room type at one property are serialised; at lodge scale this is negligible.
- Out-of-order rooms are not dated, so taking a room out of order reduces inventory for all dates until it is fixed. For planned work, use a dated room block (Phase 3.1): it takes the same room-type lock, is refused if it would oversell, and reduces inventory only on its nights.
- Modifying dates or rooms of an existing booking must go through the same lock-and-count path (Phase 2.3).
