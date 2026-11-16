# 0004 — Fixed role map in Phase 0

**Status:** Accepted, 2026-11-16 — to be superseded in Phase 1

## Context
`CLAUDE.md` calls for `roles`, `permissions` and `user_roles` tables and property-level permissions. Properties do not exist until Phase 1, so property-level grants cannot be designed yet.

## Decision
Phase 0 stores one role per membership (`organisation_users.role`) and maps roles to permissions in code (`app/modules/auth/permissions.py`). Endpoints check **permissions**, never role names.

## Consequences
- Phase 1 can replace the map with database tables and property scopes without changing endpoint code.
- Owners cannot define custom roles until then.
