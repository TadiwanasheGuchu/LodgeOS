"""Phase 0 permission model: a fixed map from role to permissions.

Phase 1 moves this into the roles, permissions and user_roles tables and adds
property-level grants (see docs/decisions/0004-phase-0-fixed-roles.md). Code should
check permissions, never role names, so that change does not touch call sites.
"""

import enum

from app.modules.organisations.models import Role


class Permission(enum.StrEnum):
    ORGANISATION_VIEW = "organisation.view"
    ORGANISATION_MANAGE = "organisation.manage"
    MEMBERS_VIEW = "members.view"
    MEMBERS_MANAGE = "members.manage"
    AUDIT_VIEW = "audit.view"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.MANAGER: frozenset(
        {
            Permission.ORGANISATION_VIEW,
            Permission.MEMBERS_VIEW,
            Permission.MEMBERS_MANAGE,
            Permission.AUDIT_VIEW,
        }
    ),
    Role.RECEPTIONIST: frozenset({Permission.ORGANISATION_VIEW}),
    Role.HOUSEKEEPING: frozenset({Permission.ORGANISATION_VIEW}),
    Role.MAINTENANCE: frozenset({Permission.ORGANISATION_VIEW}),
    Role.ACCOUNTANT: frozenset({Permission.ORGANISATION_VIEW, Permission.AUDIT_VIEW}),
}


def permissions_for(role: str) -> frozenset[Permission]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return frozenset()
