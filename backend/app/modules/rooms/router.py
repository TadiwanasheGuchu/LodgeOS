"""Room types and physical rooms."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import conflict_from_integrity, not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission
from app.modules.auth.permissions import Permission
from app.modules.properties.models import Building, RecordStatus
from app.modules.properties.router import get_property
from app.modules.rooms.models import Room, RoomType
from app.modules.rooms.schemas import (
    HousekeepingUpdate,
    MaintenanceUpdate,
    RoomBulkCreate,
    RoomCreate,
    RoomOut,
    RoomTypeCreate,
    RoomTypeOut,
    RoomTypeUpdate,
    RoomUpdate,
    check_occupancy,
)

router = APIRouter(prefix="/api/v1", tags=["rooms"])

CanView = Annotated[AuthContext, Depends(require_permission(Permission.ROOMS_VIEW))]
CanManage = Annotated[AuthContext, Depends(require_permission(Permission.ROOMS_MANAGE))]
CanHousekeep = Annotated[AuthContext, Depends(require_permission(Permission.ROOMS_HOUSEKEEPING))]
CanMaintain = Annotated[AuthContext, Depends(require_permission(Permission.ROOMS_MAINTENANCE))]

ROOM_TYPE_CONFLICTS = {
    "uq_room_types_property_id_code": "Another room type at this property already uses that code.",
    "uq_room_types_property_id_name": "Another room type at this property already has that name.",
}
ROOM_CONFLICTS = {
    "uq_rooms_property_id_number": "This property already has a room with that number."
}


def _now() -> datetime:
    return datetime.now(UTC)


async def _flush(db: DB, conflicts: dict[str, str]) -> None:
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise conflict_from_integrity(exc, conflicts) from None


# --- room types -------------------------------------------------------------------------


@router.get("/properties/{property_id}/room-types", response_model=list[RoomTypeOut])
async def list_room_types(property_id: uuid.UUID, auth: CanView, db: DB) -> list[RoomTypeOut]:
    await get_property(db, property_id)
    counts = (
        select(Room.room_type_id, func.count().label("n"))
        .where(Room.status == RecordStatus.ACTIVE)
        .group_by(Room.room_type_id)
        .subquery()
    )
    rows = await db.execute(
        select(RoomType, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.room_type_id == RoomType.id)
        .where(RoomType.property_id == property_id)
        .order_by(RoomType.status, RoomType.sort_order, RoomType.name)
    )
    return [
        RoomTypeOut.model_validate(rt).model_copy(update={"room_count": n}) for rt, n in rows.all()
    ]


@router.post(
    "/properties/{property_id}/room-types",
    response_model=RoomTypeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_room_type(
    property_id: uuid.UUID, body: RoomTypeCreate, auth: CanManage, request: Request, db: DB
) -> RoomType:
    prop = await get_property(db, property_id)
    rt = RoomType(organisation_id=prop.organisation_id, property_id=prop.id, **body.model_dump())
    db.add(rt)
    await _flush(db, ROOM_TYPE_CONFLICTS)
    await audit.record(
        db,
        action="room_type.created",
        organisation_id=prop.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="room_type",
        entity_id=rt.id,
        data={"name": rt.name, "code": rt.code, "property_id": str(prop.id)},
        ip_address=client_ip(request),
    )
    return rt


@router.patch("/room-types/{room_type_id}", response_model=RoomTypeOut)
async def update_room_type(
    room_type_id: uuid.UUID, body: RoomTypeUpdate, auth: CanManage, request: Request, db: DB
) -> RoomType:
    rt = await db.get(RoomType, room_type_id)
    if rt is None:
        raise not_found("Room type")
    changes = body.model_dump(exclude_unset=True)
    if any(v is None for k, v in changes.items() if k not in {"description", "bed_configuration"}):
        raise HTTPException(status_code=422, detail="Only description and beds can be cleared.")

    merged = {
        k: changes.get(k, getattr(rt, k))
        for k in ("base_occupancy", "max_occupancy", "max_adults", "max_children")
    }
    try:
        check_occupancy(
            merged["base_occupancy"],
            merged["max_occupancy"],
            merged["max_adults"],
            merged["max_children"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    if changes.get("status") == RecordStatus.ARCHIVED and rt.status == RecordStatus.ACTIVE:
        active_rooms = await db.scalar(
            select(func.count())
            .select_from(Room)
            .where(Room.room_type_id == rt.id, Room.status == RecordStatus.ACTIVE)
        )
        if active_rooms:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{active_rooms} active room(s) use this type. Move or archive them first.",
            )

    diff = audit.apply_changes(rt, changes)
    if diff["after"]:
        await _flush(db, ROOM_TYPE_CONFLICTS)
        await audit.record(
            db,
            action="room_type.updated",
            organisation_id=rt.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="room_type",
            entity_id=rt.id,
            data=diff,
            ip_address=client_ip(request),
        )
    return rt


# --- rooms ------------------------------------------------------------------------------


def _room_query() -> Select[Room, str, str, str]:
    return (
        select(Room, RoomType.code, RoomType.name, Building.name)
        .join(RoomType, RoomType.id == Room.room_type_id)
        .outerjoin(Building, Building.id == Room.building_id)
    )


def _room_out(room: Room, type_code: str, type_name: str, building: str | None) -> RoomOut:
    return RoomOut(
        id=room.id,
        property_id=room.property_id,
        number=room.number,
        floor=room.floor,
        notes=room.notes,
        status=room.status,
        room_type_id=room.room_type_id,
        room_type_code=type_code,
        room_type_name=type_name,
        building_id=room.building_id,
        building_name=building,
        housekeeping_status=room.housekeeping_status,
        housekeeping_updated_at=room.housekeeping_updated_at,
        maintenance_status=room.maintenance_status,
        maintenance_reason=room.maintenance_reason,
        maintenance_updated_at=room.maintenance_updated_at,
    )


async def _load_room_out(db: DB, room_id: uuid.UUID) -> RoomOut:
    row = (await db.execute(_room_query().where(Room.id == room_id))).first()
    if row is None:
        raise not_found("Room")
    return _room_out(*row)


async def _check_refs(
    db: DB, property_id: uuid.UUID, room_type_id: uuid.UUID | None, building_id: uuid.UUID | None
) -> None:
    """Room type and building must exist, be active, and belong to this property.
    The database enforces the property match too; this gives a clear message."""
    if room_type_id is not None:
        rt = await db.get(RoomType, room_type_id)
        if rt is None or rt.property_id != property_id:
            raise HTTPException(status_code=422, detail="Choose a room type from this property.")
        if rt.status != RecordStatus.ACTIVE:
            raise HTTPException(status_code=422, detail="That room type is archived.")
    if building_id is not None:
        b = await db.get(Building, building_id)
        if b is None or b.property_id != property_id:
            raise HTTPException(status_code=422, detail="Choose a building from this property.")
        if b.status != RecordStatus.ACTIVE:
            raise HTTPException(status_code=422, detail="That building is archived.")


@router.get("/properties/{property_id}/rooms", response_model=list[RoomOut])
async def list_rooms(
    property_id: uuid.UUID, auth: CanView, db: DB, include_archived: bool = False
) -> list[RoomOut]:
    await get_property(db, property_id)
    stmt = _room_query().where(Room.property_id == property_id)
    if not include_archived:
        stmt = stmt.where(Room.status == RecordStatus.ACTIVE)
    # Natural order for numbers like 2, 10, 101 and labels like "Tent 3".
    stmt = stmt.order_by(
        Building.sort_order.nulls_first(),
        Building.name.nulls_first(),
        func.length(Room.number),
        Room.number,
    )
    return [_room_out(*row) for row in (await db.execute(stmt)).all()]


@router.post(
    "/properties/{property_id}/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED
)
async def create_room(
    property_id: uuid.UUID, body: RoomCreate, auth: CanManage, request: Request, db: DB
) -> RoomOut:
    prop = await get_property(db, property_id)
    await _check_refs(db, prop.id, body.room_type_id, body.building_id)
    room = Room(organisation_id=prop.organisation_id, property_id=prop.id, **body.model_dump())
    db.add(room)
    await _flush(db, ROOM_CONFLICTS)
    await audit.record(
        db,
        action="room.created",
        organisation_id=prop.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="room",
        entity_id=room.id,
        data={"number": room.number, "property_id": str(prop.id)},
        ip_address=client_ip(request),
    )
    return await _load_room_out(db, room.id)


@router.post(
    "/properties/{property_id}/rooms/bulk",
    response_model=list[RoomOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_rooms_bulk(
    property_id: uuid.UUID, body: RoomBulkCreate, auth: CanManage, request: Request, db: DB
) -> list[RoomOut]:
    """Create several rooms of one type at once. All or nothing."""
    prop = await get_property(db, property_id)
    await _check_refs(db, prop.id, body.room_type_id, body.building_id)
    existing = set(
        (
            await db.scalars(
                select(Room.number).where(
                    Room.property_id == prop.id, Room.number.in_(body.numbers)
                )
            )
        ).all()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"These room numbers already exist: {', '.join(sorted(existing))}.",
        )
    rooms = [
        Room(
            organisation_id=prop.organisation_id,
            property_id=prop.id,
            number=n,
            room_type_id=body.room_type_id,
            building_id=body.building_id,
            floor=body.floor,
        )
        for n in body.numbers
    ]
    db.add_all(rooms)
    await _flush(db, ROOM_CONFLICTS)  # a concurrent insert still hits the unique constraint
    await audit.record(
        db,
        action="room.bulk_created",
        organisation_id=prop.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="property",
        entity_id=prop.id,
        data={"numbers": body.numbers, "room_type_id": str(body.room_type_id)},
        ip_address=client_ip(request),
    )
    ids = [r.id for r in rooms]
    rows = (await db.execute(_room_query().where(Room.id.in_(ids)))).all()
    by_id = {row[0].id: _room_out(*row) for row in rows}
    return [by_id[i] for i in ids]


async def _get_room(db: DB, room_id: uuid.UUID) -> Room:
    room = await db.get(Room, room_id)
    if room is None:
        raise not_found("Room")
    return room


@router.patch("/rooms/{room_id}", response_model=RoomOut)
async def update_room(
    room_id: uuid.UUID, body: RoomUpdate, auth: CanManage, request: Request, db: DB
) -> RoomOut:
    room = await _get_room(db, room_id)
    changes = body.model_dump(exclude_unset=True)
    for required in ("number", "room_type_id", "status"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail=f"{required} cannot be empty.")
    await _check_refs(db, room.property_id, changes.get("room_type_id"), changes.get("building_id"))
    diff = audit.apply_changes(room, changes)
    if diff["after"]:
        await _flush(db, ROOM_CONFLICTS)
        await audit.record(
            db,
            action="room.updated",
            organisation_id=room.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="room",
            entity_id=room.id,
            data=diff,
            ip_address=client_ip(request),
        )
    return await _load_room_out(db, room.id)


@router.post("/rooms/{room_id}/housekeeping", response_model=RoomOut)
async def set_housekeeping_status(
    room_id: uuid.UUID, body: HousekeepingUpdate, auth: CanHousekeep, request: Request, db: DB
) -> RoomOut:
    room = await _get_room(db, room_id)
    previous = room.housekeeping_status
    room.housekeeping_status = body.housekeeping_status
    room.housekeeping_updated_at = _now()
    room.housekeeping_updated_by = auth.user.id
    await db.flush()
    await audit.record(
        db,
        action="room.housekeeping_changed",
        organisation_id=room.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="room",
        entity_id=room.id,
        data={"number": room.number, "from": previous, "to": body.housekeeping_status.value},
        ip_address=client_ip(request),
    )
    return await _load_room_out(db, room.id)


@router.post("/rooms/{room_id}/maintenance", response_model=RoomOut)
async def set_maintenance_status(
    room_id: uuid.UUID, body: MaintenanceUpdate, auth: CanMaintain, request: Request, db: DB
) -> RoomOut:
    room = await _get_room(db, room_id)
    previous = room.maintenance_status
    room.maintenance_status = body.maintenance_status
    room.maintenance_reason = body.reason
    room.maintenance_updated_at = _now()
    room.maintenance_updated_by = auth.user.id
    await db.flush()
    await audit.record(
        db,
        action="room.maintenance_changed",
        organisation_id=room.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="room",
        entity_id=room.id,
        data={
            "number": room.number,
            "from": previous,
            "to": body.maintenance_status.value,
            "reason": body.reason,
        },
        ip_address=client_ip(request),
    )
    return await _load_room_out(db, room.id)
