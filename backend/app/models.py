"""Imports every model so Base.metadata is complete (used by Alembic and tests)."""

from app.modules.access.models import PermissionRecord, RolePermission, RoleRecord, UserRole
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User, UserSession
from app.modules.organisations.models import Organisation, OrganisationUser
from app.modules.properties.models import Building, Property
from app.modules.rooms.models import Room, RoomType

__all__ = [
    "AuditLog",
    "Building",
    "Organisation",
    "OrganisationUser",
    "PermissionRecord",
    "Property",
    "RolePermission",
    "RoleRecord",
    "Room",
    "RoomType",
    "User",
    "UserRole",
    "UserSession",
]
