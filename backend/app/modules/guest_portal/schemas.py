import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PortalRoom(BaseModel):
    room_type: str
    rate_plan: str
    adults: int
    children: int
    total: Decimal


class PortalInvoice(BaseModel):
    number: str
    issue_date: dt.date
    total: Decimal
    credited: Decimal
    paid: Decimal
    balance: Decimal


class PortalProperty(BaseModel):
    name: str
    address: list[str]
    phone: str | None
    email: str | None
    check_in_time: dt.time
    check_out_time: dt.time
    booking_terms: str | None


class PortalBooking(BaseModel):
    reference: str
    status: str
    guest_name: str
    check_in: dt.date
    check_out: dt.date
    nights: int
    currency: str
    total: Decimal
    rooms: list[PortalRoom]
    invoices: list[PortalInvoice]
    paid: Decimal
    property: PortalProperty
    arrival_time: str | None
    message: str | None
    cancellation_requested: bool
    cancellation_reason: str | None
    can_update: bool


class ArrivalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    arrival_time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    message: str | None = Field(default=None, max_length=1000)


class CancellationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=1000)


class GuestLink(BaseModel):
    url: str
    expires_at: dt.datetime


class GuestLinkRevoked(BaseModel):
    revoked: int
    reservation_id: uuid.UUID
