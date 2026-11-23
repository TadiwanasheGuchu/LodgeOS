import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class TaskAction(BaseModel):
    """One step on a room's housekeeping for a day.

    ``assign`` sets ``assigned_to`` (null unassigns); ``start`` and ``done`` default the
    assignee to the person acting; ``decline`` needs a ``note``; ``reopen`` sends a finished
    room back to the list (for example after a failed inspection).
    """

    action: Literal["assign", "start", "done", "decline", "reopen"]
    assigned_to: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)


class TaskOut(BaseModel):
    status: str
    kind: str
    assigned_to: uuid.UUID | None
    assigned_to_name: str | None
    note: str | None
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    completed_by_name: str | None


class BoardRoom(BaseModel):
    room_id: uuid.UUID
    number: str
    floor: str | None
    building_name: str | None
    room_type_code: str
    housekeeping_status: str
    maintenance_status: str
    blocked: bool
    # What the room needs today; null when nothing (clean and vacant, or ready).
    kind: str | None
    departing: bool
    guest_left: bool  # for departures: the guest has checked out
    staying: bool
    arriving: bool
    guests: int  # adults + children of the stay that matters for the room today
    task: TaskOut | None


class Assignee(BaseModel):
    user_id: uuid.UUID
    name: str


class Board(BaseModel):
    date: dt.date
    today: dt.date
    rooms: list[BoardRoom]
    assignees: list[Assignee]
