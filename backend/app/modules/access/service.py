"""Resolving and changing who may do what, and at which property."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access.models import PermissionRecord, RolePermission, RoleRecord, UserRole
from app.modules.auth.permissions import (
    GRANTED_BY_ANY_ROLE,
    PROPERTY_PERMISSIONS,
    ROLE_PERMISSIONS,
    Permission,
)
from app.modules.organisations.models import Role

ROLE_NAMES = {
    Role.OWNER: "Owner",
    Role.MANAGER: "Manager",
    Role.RECEPTIONIST: "Receptionist",
    Role.HOUSEKEEPING: "Housekeeping",
    Role.MAINTENANCE: "Maintenance",
    Role.ACCOUNTANT: "Accountant",
}
# Used to choose a single label for display, highest first.
ROLE_RANK = [
    Role.OWNER,
    Role.MANAGER,
    Role.ACCOUNTANT,
    Role.RECEPTIONIST,
    Role.HOUSEKEEPING,
    Role.MAINTENANCE,
]


@dataclass(frozen=True)
class Assignment:
    id: uuid.UUID
    role_id: uuid.UUID
    role_key: str | None
    role_name: str
    property_id: uuid.UUID | None


@dataclass(frozen=True)
class Grants:
    """Effective permissions of one membership.

    ``everywhere`` holds permissions granted for all properties; ``by_property`` holds
    those granted for one property only.
    """

    assignments: tuple[Assignment, ...] = ()
    everywhere: frozenset[Permission] = frozenset()
    by_property: dict[uuid.UUID, frozenset[Permission]] = field(default_factory=dict)

    def has(self, permission: Permission) -> bool:
        """Granted for every property (or for the organisation itself)."""
        return permission in self.everywhere

    def has_for(self, permission: Permission, property_id: uuid.UUID) -> bool:
        return permission in self.everywhere or permission in self.by_property.get(
            property_id, frozenset()
        )

    def has_anywhere(self, permission: Permission) -> bool:
        return self.has(permission) or any(permission in p for p in self.by_property.values())

    def property_scope(self, permission: Permission) -> set[uuid.UUID] | None:
        """None means every property; otherwise the properties where it is granted."""
        if self.has(permission):
            return None
        return {pid for pid, perms in self.by_property.items() if permission in perms}

    def can_see_property(self, property_id: uuid.UUID) -> bool:
        """Any property-level permission there. Otherwise the property is reported as
        not found."""
        return bool(self.everywhere & PROPERTY_PERMISSIONS) or property_id in self.by_property

    @property
    def label(self) -> str:
        """A short description for display, e.g. "Manager" or "Receptionist (1 property)"."""
        if not self.assignments:
            return "No access"
        ranked = sorted(
            self.assignments,
            key=lambda a: (
                a.property_id is not None,
                ROLE_RANK.index(Role(a.role_key))
                if a.role_key is not None and a.role_key in Role._value2member_map_
                else 99,
            ),
        )
        top = ranked[0]
        scoped = {a.property_id for a in self.assignments if a.role_id == top.role_id}
        if None in scoped:
            return top.role_name
        n = len(scoped)
        return f"{top.role_name} ({n} {'property' if n == 1 else 'properties'})"

    @property
    def primary_role_key(self) -> str | None:
        keys = [a.role_key for a in self.assignments if a.role_key]
        for role in ROLE_RANK:
            if role.value in keys:
                return role.value
        return None


async def load_grants(db: AsyncSession, membership_id: uuid.UUID) -> Grants:
    rows = (
        await db.execute(
            select(UserRole, RoleRecord, PermissionRecord.code)
            .join(RoleRecord, RoleRecord.id == UserRole.role_id)
            .outerjoin(RolePermission, RolePermission.role_id == RoleRecord.id)
            .outerjoin(PermissionRecord, PermissionRecord.id == RolePermission.permission_id)
            .where(UserRole.membership_id == membership_id)
        )
    ).all()
    assignments: dict[uuid.UUID, Assignment] = {}
    everywhere: set[Permission] = set()
    by_property: dict[uuid.UUID, set[Permission]] = {}
    for ur, role, code in rows:
        assignments[ur.id] = Assignment(ur.id, role.id, role.key, role.name, ur.property_id)
        if code is None or code not in Permission._value2member_map_:
            continue
        perm = Permission(code)
        if ur.property_id is None or perm in GRANTED_BY_ANY_ROLE:
            everywhere.add(perm)
        else:
            by_property.setdefault(ur.property_id, set()).add(perm)
    return Grants(
        assignments=tuple(assignments.values()),
        everywhere=frozenset(everywhere),
        by_property={k: frozenset(v) for k, v in by_property.items()},
    )


async def seed_system_roles(db: AsyncSession, organisation_id: uuid.UUID) -> dict[str, RoleRecord]:
    """Create the built-in roles for a new organisation."""
    catalogue = {p.code: p.id for p in (await db.scalars(select(PermissionRecord))).all()}
    roles: dict[str, RoleRecord] = {}
    for key, perms in ROLE_PERMISSIONS.items():
        role = RoleRecord(
            organisation_id=organisation_id, key=key.value, name=ROLE_NAMES[key], is_system=True
        )
        db.add(role)
        await db.flush()
        for perm in perms:
            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=catalogue[perm.value],
                    organisation_id=organisation_id,
                )
            )
        roles[key.value] = role
    await db.flush()
    return roles


async def system_role(db: AsyncSession, organisation_id: uuid.UUID, key: str) -> RoleRecord:
    role = await db.scalar(
        select(RoleRecord).where(
            RoleRecord.organisation_id == organisation_id, RoleRecord.key == key
        )
    )
    if role is None:
        raise LookupError(f"System role {key!r} missing for organisation {organisation_id}")
    return role
