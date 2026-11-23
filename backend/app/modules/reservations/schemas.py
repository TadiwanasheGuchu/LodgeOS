import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.modules.reservations.models import BookingSource, ReservationStatus


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GuestIn(_In):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    notes: str | None = Field(default=None, max_length=2000)


class GuestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    country_code: str | None
    notes: str | None


class RoomIn(_In):
    room_type_id: uuid.UUID
    rate_plan_id: uuid.UUID
    adults: int = Field(ge=1, le=50)
    children: int = Field(default=0, ge=0, le=50)
    room_id: uuid.UUID | None = None


class ReservationCreate(_In):
    check_in: date
    check_out: date
    # Either an existing guest or the details of a new one.
    guest_id: uuid.UUID | None = None
    guest: GuestIn | None = None
    rooms: list[RoomIn] = Field(min_length=1, max_length=20)
    status: ReservationStatus = ReservationStatus.CONFIRMED
    source: BookingSource = BookingSource.PHONE
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _guest_and_dates(self) -> Self:
        if (self.guest_id is None) == (self.guest is None):
            raise ValueError("Give either an existing guest or a new guest's details.")
        if self.check_out <= self.check_in:
            raise ValueError("Check-out must be after check-in.")
        return self


class StatusChange(_In):
    reason: str | None = Field(default=None, min_length=3, max_length=500)


class ReservationRoomOut(BaseModel):
    id: uuid.UUID
    room_type_id: uuid.UUID
    room_type_name: str
    room_id: uuid.UUID | None
    room_number: str | None
    rate_plan_id: uuid.UUID
    adults: int
    children: int
    total_amount: Decimal
    tax_amount: Decimal
    price_snapshot: dict[str, Any]


class StatusChangeOut(BaseModel):
    from_status: str | None
    to_status: str
    reason: str | None
    changed_by_name: str | None
    changed_at: datetime


class ReservationSummary(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    reference: str
    status: str
    source: str
    guest_id: uuid.UUID
    guest_name: str
    check_in: date
    check_out: date
    nights: int
    room_count: int
    currency: str
    total_amount: Decimal
    created_at: datetime


class ReservationDetail(ReservationSummary):
    tax_amount: Decimal
    notes: str | None
    cancellation_reason: str | None
    guest: GuestOut
    rooms: list[ReservationRoomOut]
    history: list[StatusChangeOut]


class NightOut(BaseModel):
    night: date
    sellable: int
    booked: int
    free: int


class RoomTypeAvailability(BaseModel):
    room_type_id: uuid.UUID
    room_type_name: str
    room_type_code: str
    max_occupancy: int
    free: int  # the minimum over the nights: how many can be booked for the whole stay
    nights: list[NightOut]


class AssignRoom(_In):
    # null removes the allocation (the booking keeps its room type).
    room_id: uuid.UUID | None


class FreeRoom(BaseModel):
    id: uuid.UUID
    number: str
    building_name: str | None
    floor: str | None
    housekeeping_status: str
    maintenance_status: str


class CalendarStay(BaseModel):
    reservation_room_id: uuid.UUID
    reservation_id: uuid.UUID
    reference: str
    status: str
    guest_name: str
    room_type_id: uuid.UUID
    room_id: uuid.UUID | None
    check_in: date
    check_out: date
    adults: int
    children: int


class CalendarRoom(BaseModel):
    id: uuid.UUID
    number: str
    room_type_id: uuid.UUID
    room_type_code: str
    building_name: str | None
    housekeeping_status: str
    maintenance_status: str


class CalendarOut(BaseModel):
    start: date
    days: int
    rooms: list[CalendarRoom]
    stays: list[CalendarStay]


class TodayOut(BaseModel):
    date: date
    arrivals: list[ReservationSummary]
    departures: list[ReservationSummary]
    in_house: int
    unassigned_arrivals: int


class DateChange(_In):
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def _order(self) -> Self:
        if self.check_out <= self.check_in:
            raise ValueError("Check-out must be after check-in.")
        return self


class GuestUpdate(_In):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    notes: str | None = Field(default=None, max_length=2000)
