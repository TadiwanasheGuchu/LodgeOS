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
from app.modules.guest_portal.models import GuestAccessToken
from app.modules.guests.models import Guest
from app.modules.housekeeping.models import HousekeepingTask
from app.modules.invoicing.models import (
    CreditNote,
    CreditNoteItem,
    DocumentSequence,
    Invoice,
    InvoiceItem,
)
from app.modules.maintenance.models import MaintenanceTicket, RoomBlock
from app.modules.notifications.models import Notification
from app.modules.organisations.models import Organisation, OrganisationUser
from app.modules.payments.models import Payment, PaymentAllocation, Refund
from app.modules.properties.models import Building, Property
from app.modules.rates.models import RatePlan, RatePlanPrice, SeasonalRate, Tax
from app.modules.reservations.models import Reservation, ReservationRoom, ReservationStatusChange
from app.modules.rooms.models import Room, RoomType

__all__ = [
    "AuditLog",
    "Building",
    "CreditNote",
    "CreditNoteItem",
    "DocumentSequence",
    "Guest",
    "GuestAccessToken",
    "HousekeepingTask",
    "Invitation",
    "Invoice",
    "InvoiceItem",
    "MaintenanceTicket",
    "Notification",
    "Organisation",
    "OrganisationUser",
    "Payment",
    "PaymentAllocation",
    "PermissionRecord",
    "Property",
    "RatePlan",
    "RatePlanPrice",
    "Refund",
    "Reservation",
    "ReservationRoom",
    "ReservationStatusChange",
    "RolePermission",
    "RoleRecord",
    "Room",
    "RoomBlock",
    "RoomType",
    "SeasonalRate",
    "Tax",
    "User",
    "UserRole",
    "UserSession",
]
