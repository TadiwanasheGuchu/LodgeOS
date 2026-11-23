import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Key = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class PublicImage(BaseModel):
    alt: str
    urls: dict[str, str]
    widths: dict[str, int]


class PublicRoomType(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    bed_configuration: str | None
    max_occupancy: int
    max_adults: int
    max_children: int
    photos: list[PublicImage] = []


class PublicProperty(BaseModel):
    name: str
    property_type: str
    description: str | None
    address: list[str]
    phone: str | None
    email: str | None
    check_in_time: dt.time
    check_out_time: dt.time
    currency: str
    timezone: str
    booking_mode: str
    booking_terms: str
    today: dt.date
    earliest_arrival: dt.date
    latest_arrival: dt.date
    room_types: list[PublicRoomType]
    logo: PublicImage | None = None
    photos: list[PublicImage] = []


class Offer(BaseModel):
    rate_plan_id: uuid.UUID
    name: str
    description: str | None
    meal_plan: str
    total: Decimal
    tax_included: Decimal
    nights: int


class RoomTypeOffers(BaseModel):
    room_type_id: uuid.UUID
    name: str
    available: int
    offers: list[Offer]


class PublicRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_type_id: uuid.UUID
    rate_plan_id: uuid.UUID
    adults: int = Field(ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)


class PublicGuest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")


class PublicBookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    check_in: dt.date
    check_out: dt.date
    rooms: list[PublicRoom] = Field(min_length=1, max_length=4)
    guest: PublicGuest
    special_requests: str | None = Field(default=None, max_length=1000)
    accept_terms: bool
    # Honeypot: hidden from people, filled in by naive bots.
    website: str = Field(default="", max_length=200)
    idempotency_key: Key


class PublicBookingRoom(BaseModel):
    room_type: str
    rate_plan: str
    adults: int
    children: int
    total: Decimal


class PublicBooking(BaseModel):
    reference: str
    status: str
    check_in: dt.date
    check_out: dt.date
    nights: int
    currency: str
    total: Decimal
    rooms: list[PublicBookingRoom]
    guest_name: str
    email: str
    hold_expires_at: dt.datetime | None
