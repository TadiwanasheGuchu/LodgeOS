# 0005 — Frontend served same-origin, rendered per request

**Status:** Accepted, 2026-11-16

## Context
Sessions are HttpOnly, SameSite=Lax cookies (ADR-0003). If the browser called the API on a different site, cookies would need SameSite=None and CORS with credentials, widening the attack surface. Next.js 16 enables Cache Components by default, which is designed around static shells and cached data.

## Decision
- The browser talks only to the Next.js origin. `next.config.ts` rewrites `/api/*` to the API (`LODGEOS_API_ORIGIN`). Server components call the API directly, forwarding the visitor's cookies.
- Cache Components is turned off. Every LodgeOS screen depends on the signed-in user and is rendered per request; a nonce-based CSP also requires dynamic rendering.
- Navigation and page-level checks hide what a role cannot use, but the API remains the authority on every permission.

## Consequences
- Cookies are first-party; CSP can use `connect-src 'self'`.
- One extra hop (Next.js → API) per browser API call. Acceptable; revisit with a reverse-proxy route in production if latency matters.
- The public booking engine (Phase 4) may want static, cached pages; it can opt into caching per route then.
