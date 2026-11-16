import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RoleOut(BaseModel):
    id: uuid.UUID
    key: str | None
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]


class AssignmentOut(BaseModel):
    id: uuid.UUID
    role_id: uuid.UUID
    role_key: str | None
    role_name: str
    property_id: uuid.UUID | None
    property_name: str | None


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    # Highest system role key and a display label, kept for simple displays.
    role: str
    role_label: str
    status: str
    created_at: datetime
    assignments: list[AssignmentOut]


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: uuid.UUID
    property_id: uuid.UUID | None = None


class MemberStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "disabled"]
