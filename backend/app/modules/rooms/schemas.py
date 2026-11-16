import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.properties.models import RecordStatus
from app.modules.rooms.models import HousekeepingStatus, MaintenanceStatus

RoomNumber = Annotated[
    str, Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9 ._/-]*$")
]


class RoomTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=100)
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9-]{0,9}$")
    description: str | None = Field(default=None, max_length=2000)
    bed_configuration: str | None = Field(default=None, max_length=200)
    base_occupancy: int = Field(ge=1, le=50)
    max_occupancy: int = Field(ge=1, le=50)
    max_adults: int = Field(ge=1, le=50)
    max_children: int = Field(default=0, ge=0, le=50)
    sort_order: int = Field(default=0, ge=0, le=10_000)

    @model_validator(mode="after")
    def _occupancy(self) -> Self:
        check_occupancy(self.base_occupancy, self.max_occupancy, self.max_adults, self.max_children)
        return self


class RoomTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=100)
    code: str | None = Field(default=None, pattern=r"^[A-Z0-9][A-Z0-9-]{0,9}$")
    description: str | None = Field(default=None, max_length=2000)
    bed_configuration: str | None = Field(default=None, max_length=200)
    base_occupancy: int | None = Field(default=None, ge=1, le=50)
    max_occupancy: int | None = Field(default=None, ge=1, le=50)
    max_adults: int | None = Field(default=None, ge=1, le=50)
    max_children: int | None = Field(default=None, ge=0, le=50)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    status: RecordStatus | None = None


def check_occupancy(base: int, max_occ: int, adults: int, children: int) -> None:
    if max_occ < base:
        raise ValueError("Maximum guests must be at least the number included in the base rate.")
    if adults > max_occ:
        raise ValueError("Maximum adults cannot exceed maximum guests.")
    if children > max_occ:
        raise ValueError("Maximum children cannot exceed maximum guests.")


class RoomTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID
    name: str
    code: str
    description: str | None
    bed_configuration: str | None
    base_occupancy: int
    max_occupancy: int
    max_adults: int
    max_children: int
    sort_order: int
    status: str
    room_count: int = 0


class RoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    number: RoomNumber
    room_type_id: uuid.UUID
    building_id: uuid.UUID | None = None
    floor: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)


class RoomBulkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    numbers: list[RoomNumber] = Field(min_length=1, max_length=200)
    room_type_id: uuid.UUID
    building_id: uuid.UUID | None = None
    floor: str | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        seen: set[str] = set()
        dupes = sorted({n for n in self.numbers if n in seen or seen.add(n)})  # type: ignore[func-returns-value]
        if dupes:
            raise ValueError(f"Room numbers repeated in the list: {', '.join(dupes)}.")
        return self


class RoomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    number: RoomNumber | None = None
    room_type_id: uuid.UUID | None = None
    building_id: uuid.UUID | None = None
    floor: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=2000)
    status: RecordStatus | None = None


class HousekeepingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    housekeeping_status: HousekeepingStatus


class MaintenanceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    maintenance_status: MaintenanceStatus
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _reason(self) -> Self:
        if self.maintenance_status == MaintenanceStatus.NONE:
            self.reason = None
        elif not self.reason:
            raise ValueError("Give a reason so the team knows what is wrong.")
        return self


class RoomOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    number: str
    floor: str | None
    notes: str | None
    status: str
    room_type_id: uuid.UUID
    room_type_code: str
    room_type_name: str
    building_id: uuid.UUID | None
    building_name: str | None
    housekeeping_status: str
    housekeeping_updated_at: datetime | None
    maintenance_status: str
    maintenance_reason: str | None
    maintenance_updated_at: datetime | None
