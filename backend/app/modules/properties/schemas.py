import re
import uuid
from datetime import datetime, time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.organisations.schemas import validate_timezone
from app.modules.properties.models import PropertyType, RecordStatus

Slug = Annotated[str, Field(min_length=2, max_length=63, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Country = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
OptionalText = Annotated[str | None, Field(default=None, max_length=200)]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:63].strip("-") or "property"


class _PropertyFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    address_line1: OptionalText = None
    address_line2: OptionalText = None
    city: Annotated[str | None, Field(default=None, max_length=100)] = None
    region: Annotated[str | None, Field(default=None, max_length=100)] = None
    postal_code: Annotated[str | None, Field(default=None, max_length=20)] = None
    phone: Annotated[str | None, Field(default=None, max_length=40)] = None
    email: EmailStr | None = None
    legal_name: Annotated[str | None, Field(default=None, max_length=200)] = None
    tax_number: Annotated[str | None, Field(default=None, max_length=50)] = None


class PropertyCreate(_PropertyFields):
    name: str = Field(min_length=2, max_length=200)
    slug: Slug | None = None
    property_type: PropertyType
    # Default to the organisation's timezone and currency when omitted.
    timezone: str | None = None
    currency: Currency | None = None
    country_code: Country | None = None
    check_in_time: time = time(14, 0)
    check_out_time: time = time(10, 0)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        return validate_timezone(v) if v is not None else None


class PropertyUpdate(_PropertyFields):
    # Public booking engine (ADR-0012).
    booking_engine_enabled: bool | None = None
    booking_mode: Literal["request", "instant"] | None = None
    public_description: str | None = Field(default=None, max_length=4000)
    booking_terms: str | None = Field(default=None, max_length=8000)
    min_lead_days: int | None = Field(default=None, ge=0, le=365)
    max_advance_days: int | None = Field(default=None, ge=1, le=730)
    request_hold_hours: int | None = Field(default=None, ge=1, le=336)

    name: str | None = Field(default=None, min_length=2, max_length=200)
    property_type: PropertyType | None = None
    status: RecordStatus | None = None
    timezone: str | None = None
    currency: Currency | None = None
    country_code: Country | None = None
    check_in_time: time | None = None
    check_out_time: time | None = None
    # ISO weekdays of nights that use weekend prices (1 = Monday ... 7 = Sunday).
    weekend_nights: list[Annotated[int, Field(ge=1, le=7)]] | None = Field(
        default=None, max_length=7
    )

    @field_validator("weekend_nights")
    @classmethod
    def _unique_sorted(cls, v: list[int] | None) -> list[int] | None:
        return sorted(set(v)) if v is not None else None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        return validate_timezone(v) if v is not None else None


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    property_type: str
    status: str
    timezone: str
    currency: str
    country_code: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    phone: str | None
    email: str | None
    legal_name: str | None
    tax_number: str | None
    booking_engine_enabled: bool
    booking_mode: str
    public_description: str | None
    booking_terms: str | None
    min_lead_days: int
    max_advance_days: int
    request_hold_hours: int
    check_in_time: time
    check_out_time: time
    weekend_nights: list[int]
    created_at: datetime


class PropertySummary(PropertyOut):
    room_count: int
    room_type_count: int


class BuildingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=10_000)


class BuildingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    status: RecordStatus | None = None


class BuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID
    name: str
    description: str | None
    sort_order: int
    status: str
