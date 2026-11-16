"""Imports every model so Base.metadata is complete (used by Alembic and tests)."""

from app.modules.access.models import (
    Invitation,
    PermissionRecord,
    RolePermission,
    RoleRecord,
    UserRole,
)
from app.modules.audit.models import AuditLog
from app.modules.auth.models import User, UserSession
from app.modules.guests.models import Guest
from app.modules.organisations.models import Organisation, OrganisationUser
from app.modules.properties.models import Building, Property
from app.modules.rates.models import RatePlan, RatePlanPrice, SeasonalRate, Tax
from app.modules.reservations.models import Reservation, ReservationRoom, ReservationStatusChange
from app.modules.rooms.models import Room, RoomType

__all__ = [
    "AuditLog",
    "Building",
    "Guest",
    "Invitation",
    "Organisation",
    "OrganisationUser",
    "PermissionRecord",
    "Property",
    "RatePlan",
    "RatePlanPrice",
    "Reservation",
    "ReservationRoom",
    "ReservationStatusChange",
    "RolePermission",
    "RoleRecord",
    "Room",
    "RoomType",
    "SeasonalRate",
    "Tax",
    "User",
    "UserRole",
    "UserSession",
]
