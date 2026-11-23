import uuid
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.maintenance.models import TicketPriority, TicketStatus


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TicketCreate(_In):
    room_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    priority: TicketPriority = TicketPriority.NORMAL

    @model_validator(mode="after")
    def _where(self) -> Self:
        if self.room_id is None and not self.location:
            raise ValueError("Say which room or area has the problem.")
        return self


class TicketUpdate(_In):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assigned_to: uuid.UUID | None = None
    resolution: str | None = Field(default=None, max_length=4000)


class BlockCreate(_In):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _order(self) -> Self:
        if self.end_date <= self.start_date:
            raise ValueError("The room must come back on a later date than it goes out.")
        return self


class BlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    ticket_id: uuid.UUID | None
    start_date: date
    end_date: date
    reason: str
    status: str


class TicketOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    room_id: uuid.UUID | None
    room_number: str | None
    location: str | None
    title: str
    description: str | None
    priority: str
    status: str
    reported_by_name: str
    assigned_to: uuid.UUID | None
    assigned_to_name: str | None
    resolution: str | None
    created_at: datetime
    closed_at: datetime | None
    blocks: list[BlockOut]
