# 0006 — Database roles and property-level access

**Status:** Accepted, 2026-11-16. Supersedes ADR-0004.

## Context
Groups run several properties. A receptionist at one lodge must not see another lodge's rooms, and owners need to manage staff without a developer.

## Decision
- `permissions` is a global catalogue mirroring `Permission` in code (a test fails if they drift; changes need a migration). `roles` belong to an organisation; six system roles are created for each organisation and cannot be edited. `user_roles` grants a role to a membership for **all properties** (`property_id` NULL) or **one property**.
- Property-level permissions (`properties.*`, `rooms.*`) follow the grant's scope. `organisation.view` is granted organisation-wide by any role. Sensitive organisation-level permissions (staff, activity log, settings) need an organisation-wide grant.
- A property where the caller holds no property-level permission is reported as **not found**, the same as another tenant's.
- Escalation rule: you may grant, remove, or disable only what is within the permissions you hold for every property. The last active owner cannot be removed or disabled; nobody can change their own access.
- Property scope is enforced in the application. RLS continues to enforce the organisation boundary. RLS additionally lets a user read their own memberships, role assignments and role names in other organisations (for the organisation picker); every endpoint acting on the active organisation filters by it explicitly.
- Staff join by invitation link (no email provider yet). Tokens are stored as SHA-256, expire after 7 days and work once. An existing account must give its own password to accept.

## Consequences
- Per-property staff are possible today; custom roles need only an editor UI.
- Every new property-level endpoint must call `auth.require_for_property(...)` (or `get_property(..., permission)`); tests cover the pattern.
- RLS does not yet enforce property scope; a later ADR may add property-level policies if a module needs defence in depth there.
