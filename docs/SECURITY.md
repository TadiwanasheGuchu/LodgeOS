# Security

This document records what is implemented and verified, and what is planned. Do not move an item to "implemented" without a test.

## Implemented (Phase 0)

| Control | Implementation | Verified by |
|---|---|---|
| Password hashing | Argon2id (argon2-cffi defaults, RFC 9106 low-memory profile); automatic rehash on login when parameters change | `test_password_hash_is_argon2id_and_verifies` |
| Account enumeration | Unknown email and wrong password return the same 401 body; unknown emails are verified against a dummy hash for similar timing | `test_wrong_password_and_unknown_email_get_the_same_answer` |
| Sessions | Server-side; 256-bit random token in an `HttpOnly`, `SameSite=Lax`, `Secure` cookie; only SHA-256 of the token is stored; 12 h idle and 7 d absolute expiry; revoked on logout | `test_logout_revokes_the_session`, `test_idle_and_absolute_expiry` |
| CSRF | Double-submit cookie (`lodgeos_csrf` + `X-CSRF-Token`), constant-time comparison; rotated on login | `test_state_changing_requests_need_csrf_token` |
| Login throttling | Redis fixed window: 10 attempts per email and 50 per IP per 15 min; **fails closed** (503) if Redis is down | `test_login_is_throttled_per_email`, `test_login_fails_closed_when_redis_is_unavailable` |
| Tenant isolation (app) | Organisation comes only from the server-side session; unknown request fields are rejected | `test_api_only_returns_the_callers_organisation`, `test_organisation_id_in_request_body_is_ignored` |
| Tenant isolation (database) | RLS on `organisations`, `organisation_users`, `audit_logs`; runtime role cannot bypass RLS | `test_rls_*` (6 tests) |
| Least privilege | Runtime role has no `DELETE`, cannot create organisations, and cannot modify audit logs | `test_runtime_role_lacks_destructive_privileges` |
| Immediate revocation | Membership and organisation status are re-checked on every request | `test_disabling_a_membership_takes_effect_immediately`, `test_suspended_organisation_is_not_accessible` |
| RBAC | Fixed role → permission map; handlers check permissions, not role names | `test_receptionist_can_view_but_not_change`, `test_manager_sees_members_but_cannot_change_settings` |
| Audit logging | Append-only; written in the same transaction as the change; failed sign-ins recorded | `test_owner_updates_settings_and_change_is_audited` |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store` on API responses | `test_health` (partial) |
| Container | API runs as a non-root user (uid 10001) | Manual check, milestone 0.2 |
| Dependency scanning | `pip-audit` (backend) and `npm audit --omit=dev` (frontend) in CI | CI jobs `dependency-audit`, `frontend` |
| Content-Security-Policy | Per-request nonce CSP on every page (`frontend/src/proxy.ts`): `script-src 'self' 'nonce-…' 'strict-dynamic'`, `frame-ancestors 'none'`, `object-src 'none'`, `form-action 'self'`; no `unsafe-eval` in production | E2E `pages are served with a nonce-based CSP and run without violations` |
| Same-origin API | The browser calls `/api/*` on the frontend origin, forwarded to the API, so cookies are first-party; `connect-src 'self'` | E2E sign-in tests |

## Known gaps (tracked)

- **MFA**: not implemented. Planned as optional TOTP before pilot.
- **Password reset and invitations**: not implemented; accounts are created by the operator CLI.
- **Session rotation on privilege change**: switching organisation keeps the same token. Acceptable because permissions are re-evaluated per request; revisit with MFA.
- **Platform administrators**: no platform-admin role exists yet. When added, it must not get default access to tenant data (`CLAUDE.md` §8); support access will require an explicit, time-limited, audited grant.
- **Rate limiting** covers sign-in only. General API rate limiting is planned at the reverse proxy and per-route.
- **Dev-tool advisory**: `npm audit` reports 8 moderate findings in `minimatch` inside ESLint's TypeScript parser (development only, not shipped). Production dependencies report 0. Re-check when eslint-config-next updates.
- **CSP `style-src-attr 'unsafe-inline'`**: allowed for inline style attributes set by UI primitives; these cannot execute script.
- **Secrets**: development defaults exist in `docker-compose.yml` and `.env.example`; production must supply its own (see `DEPLOYMENT.md`).

## Rules for contributors

- Every new tenant-owned table calls `enable_tenant_rls()` in its migration (or documents a custom policy) and gets an RLS test.
- Never grant `DELETE` on financial or audit tables.
- Never log passwords, tokens, card data or full guest records. Audit `data` holds IDs and changed fields only.
- Webhook endpoints live under `/api/v1/webhooks/` (exempt from CSRF) and must verify provider signatures and idempotency keys.
