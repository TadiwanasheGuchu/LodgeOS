# 0003 — Server-side sessions with cookie and CSRF token

**Status:** Accepted, 2026-11-16

## Context
The main clients are our own browser apps. Staff must be able to be signed out immediately (a dismissed employee, a lost tablet), and a token stored in browser JavaScript is exposed to any XSS.

## Decision
- Opaque 256-bit session tokens in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie. Only the SHA-256 is stored in `user_sessions`.
- Idle timeout 12 h (front-desk shifts), absolute timeout 7 days.
- CSRF via double-submit cookie (`lodgeos_csrf` + `X-CSRF-Token`) on every unsafe method under `/api/`.
- JWTs are not used for staff sessions.

## Consequences
- Logout and revocation are immediate.
- One indexed lookup per request; `last_seen_at` is written at most once a minute.
- The frontend must be served from the same site as the API, or behind the same reverse proxy, for cookies to flow. A future public or partner API will use separate API keys.
