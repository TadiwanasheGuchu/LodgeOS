# 0013 — Guest portal through secret links

**Status:** Accepted, 2026-11-23

## Context
Guests want to see their booking, invoice and balance, and tell the lodge when they arrive, without creating an account. Many guests in the region communicate through WhatsApp, so staff need a link they can paste into a chat. The link must not expose any other booking, and must stop working when the stay is long over or staff withdraw it.

## Decision
- **Secret link per booking.** `/stay/{token}` where the token is 32 random bytes (URL-safe). Only its SHA-256 hash is stored in `guest_access_tokens`, never the token itself; a database leak gives no working links. A booking may have several tokens (one per email or per shared link).
- **Expiry and revocation.** A token works until 30 days after check-out, and staff can revoke every link of a booking at once. Tokens for cancelled bookings keep working so the guest can see the cancellation, until they expire.
- **Tenant context.** A `SECURITY DEFINER` function `guest_portal_access(token_hash)` returns the organisation and reservation ids for a valid token and nothing else. The request then runs under that organisation's RLS context with no user, and reads only that reservation and its own invoices and payments.
- **What the guest sees:** property contact details, booking reference, status, dates, rooms and total, issued invoices with paid amount and balance, and the booking terms. Never staff notes, other guests or internal ids beyond what links need.
- **What the guest can do:** give an estimated arrival time and a message (stored on the booking and shown to staff as "From the guest"), and ask to cancel with a reason. Cancellation stays a staff decision under the property's terms; the request is flagged on the booking.
- **Links reach the guest** in every booking confirmation email (staff-sent and website), and through "Share guest link" on the booking (copy or WhatsApp). Creating, sharing and revoking links are audited without the token.
- **Abuse limits:** 60 portal requests per minute per IP; guest updates limited to 10 per hour per booking; tokens are unguessable (256 bits).

## Consequences
- Anyone holding the link can see the booking, like a booking reference with a password in it. Guests are told to keep it private; staff can revoke it.
- Online payment of the balance (Phase 4.3) will be offered from the portal once a gateway is chosen.
