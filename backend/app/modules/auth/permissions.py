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
    RATES_VIEW = "rates.view"
    RATES_MANAGE = "rates.manage"
    RESERVATIONS_VIEW = "reservations.view"
    RESERVATIONS_MANAGE = "reservations.manage"
    INVOICES_VIEW = "invoices.view"
    INVOICES_MANAGE = "invoices.manage"
    INVOICES_CREDIT = "invoices.credit"
    PAYMENTS_VIEW = "payments.view"
    PAYMENTS_MANAGE = "payments.manage"
    PAYMENTS_REFUND = "payments.refund"
    POS_SELL = "pos.sell"
    POS_MANAGE = "pos.manage"


# Permissions about a property's setup and rooms. When a role is granted for one property,
# these apply to that property only.
PROPERTY_PERMISSIONS: frozenset[Permission] = frozenset(
    p
    for p in Permission
    if p.value.startswith(
        ("properties.", "rooms.", "rates.", "reservations.", "invoices.", "payments.", "pos.")
    )
)

# Organisation-level permissions that any role grant carries organisation-wide, because
# every staff member needs them to use the app at all. Sensitive organisation-level
# permissions (staff, activity log, settings) need an organisation-wide grant.
GRANTED_BY_ANY_ROLE: frozenset[Permission] = frozenset({Permission.ORGANISATION_VIEW})

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
            Permission.RATES_VIEW,
            Permission.RATES_MANAGE,
            Permission.RESERVATIONS_VIEW,
            Permission.RESERVATIONS_MANAGE,
            Permission.INVOICES_VIEW,
            Permission.INVOICES_MANAGE,
            Permission.INVOICES_CREDIT,
            Permission.PAYMENTS_VIEW,
            Permission.PAYMENTS_MANAGE,
            Permission.PAYMENTS_REFUND,
            Permission.POS_SELL,
            Permission.POS_MANAGE,
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
            Permission.RATES_VIEW,
            Permission.RESERVATIONS_VIEW,
            Permission.RESERVATIONS_MANAGE,
            Permission.INVOICES_VIEW,
            Permission.INVOICES_MANAGE,
            Permission.PAYMENTS_VIEW,
            Permission.PAYMENTS_MANAGE,
            Permission.POS_SELL,
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
        {
            Permission.ORGANISATION_VIEW,
            Permission.AUDIT_VIEW,
            Permission.PROPERTIES_VIEW,
            Permission.RATES_VIEW,
            Permission.RESERVATIONS_VIEW,
            Permission.INVOICES_VIEW,
            Permission.INVOICES_MANAGE,
            Permission.INVOICES_CREDIT,
            Permission.PAYMENTS_VIEW,
            Permission.PAYMENTS_MANAGE,
            Permission.PAYMENTS_REFUND,
        }
    ),
}


def permissions_for(role: str) -> frozenset[Permission]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return frozenset()
