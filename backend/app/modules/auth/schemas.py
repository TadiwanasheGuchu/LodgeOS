import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.core.security import MAX_PASSWORD_LENGTH


class LoginRequest(BaseModel):
    # Not validated as an email address here: sign-in only looks the account up, and
    # format rules belong to account creation. A stricter check would lock out accounts
    # created under older rules.
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class SwitchOrganisationRequest(BaseModel):
    organisation_id: uuid.UUID


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str


class MembershipOut(BaseModel):
    organisation_id: uuid.UUID
    organisation_name: str
    organisation_slug: str
    # Highest system role key ("owner", "manager", ...), or "" if only custom roles.
    role: str
    role_label: str


class ActiveOrganisationOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    role: str
    role_label: str
    # Granted for every property.
    permissions: list[str]
    # Granted for specific properties only: {property_id: [permission, ...]}.
    property_permissions: dict[uuid.UUID, list[str]]


class MeResponse(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]
    active_organisation: ActiveOrganisationOut | None
