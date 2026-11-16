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
    PROPERTIES_VIEW = "properties.view"
    PROPERTIES_MANAGE = "properties.manage"
    ROOMS_VIEW = "rooms.view"
    ROOMS_MANAGE = "rooms.manage"
    ROOMS_HOUSEKEEPING = "rooms.housekeeping_update"
    ROOMS_MAINTENANCE = "rooms.maintenance_update"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(Permission),
    Role.MANAGER: frozenset(
        {
            Permission.ORGANISATION_VIEW,
            Permission.MEMBERS_VIEW,
            Permission.MEMBERS_MANAGE,
            Permission.AUDIT_VIEW,
            Permission.PROPERTIES_VIEW,
            Permission.PROPERTIES_MANAGE,
            Permission.ROOMS_VIEW,
            Permission.ROOMS_MANAGE,
            Permission.ROOMS_HOUSEKEEPING,
            Permission.ROOMS_MAINTENANCE,
        }
    ),
    # Front desk marks rooms clean after a quick check and reports faults, but does not
    # change property setup.
    Role.RECEPTIONIST: frozenset(
        {
            Permission.ORGANISATION_VIEW,
            Permission.PROPERTIES_VIEW,
            Permission.ROOMS_VIEW,
            Permission.ROOMS_HOUSEKEEPING,
        }
    ),
    Role.HOUSEKEEPING: frozenset(
        {
            Permission.ORGANISATION_VIEW,
            Permission.PROPERTIES_VIEW,
            Permission.ROOMS_VIEW,
            Permission.ROOMS_HOUSEKEEPING,
        }
    ),
    Role.MAINTENANCE: frozenset(
        {
            Permission.ORGANISATION_VIEW,
            Permission.PROPERTIES_VIEW,
            Permission.ROOMS_VIEW,
            Permission.ROOMS_MAINTENANCE,
        }
    ),
    Role.ACCOUNTANT: frozenset(
        {Permission.ORGANISATION_VIEW, Permission.AUDIT_VIEW, Permission.PROPERTIES_VIEW}
    ),
}


def permissions_for(role: str) -> frozenset[Permission]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return frozenset()
