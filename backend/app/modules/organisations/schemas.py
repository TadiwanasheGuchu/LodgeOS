import uuid
from datetime import datetime
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator

_TIMEZONES = frozenset(available_timezones())


def validate_timezone(value: str) -> str:
    if value not in _TIMEZONES:
        raise ValueError("Unknown IANA timezone, for example Africa/Windhoek.")
    return value


class OrganisationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    default_currency: str
    default_timezone: str
    country_code: str | None
    created_at: datetime


class OrganisationUpdate(BaseModel):
    """Only fields an organisation owner may change. Slug and status are platform-managed."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=200)
    default_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    default_timezone: str | None = None
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")

    @field_validator("default_timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        return validate_timezone(v) if v is not None else None


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    status: str
    created_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    actor_user_id: uuid.UUID | None
    actor_name: str | None = None
    entity_type: str | None
    entity_id: uuid.UUID | None
    data: dict[str, object]
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    next_cursor: str | None
