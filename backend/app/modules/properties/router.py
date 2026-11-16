"""Properties and buildings of the caller's organisation."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import conflict_from_integrity, not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission
from app.modules.auth.permissions import Permission
from app.modules.organisations.models import Organisation
from app.modules.properties.models import Building, Property, RecordStatus
from app.modules.properties.schemas import (
    BuildingCreate,
    BuildingOut,
    BuildingUpdate,
    PropertyCreate,
    PropertyOut,
    PropertySummary,
    PropertyUpdate,
    slugify,
)
from app.modules.rooms.models import Room, RoomType

router = APIRouter(prefix="/api/v1", tags=["properties"])

CanView = Annotated[AuthContext, Depends(require_permission(Permission.PROPERTIES_VIEW))]
CanManage = Annotated[AuthContext, Depends(require_permission(Permission.PROPERTIES_MANAGE))]

PROPERTY_CONFLICTS = {
    "uq_properties_organisation_id_slug": "Another property already uses this short name (slug).",
}
BUILDING_CONFLICTS = {
    "uq_buildings_property_id_name": "This property already has a building with that name."
}


async def get_property(db: DB, property_id: uuid.UUID) -> Property:
    # RLS limits this to the caller's organisation; another tenant's id is simply not found.
    prop = await db.get(Property, property_id)
    if prop is None:
        raise not_found("Property")
    return prop


@router.get("/properties", response_model=list[PropertySummary])
async def list_properties(
    auth: CanView, db: DB, include_archived: bool = False
) -> list[PropertySummary]:
    room_counts = (
        select(Room.property_id, func.count().label("n"))
        .where(Room.status == RecordStatus.ACTIVE)
        .group_by(Room.property_id)
        .subquery()
    )
    type_counts = (
        select(RoomType.property_id, func.count().label("n"))
        .where(RoomType.status == RecordStatus.ACTIVE)
        .group_by(RoomType.property_id)
        .subquery()
    )
    stmt = (
        select(Property, func.coalesce(room_counts.c.n, 0), func.coalesce(type_counts.c.n, 0))
        .outerjoin(room_counts, room_counts.c.property_id == Property.id)
        .outerjoin(type_counts, type_counts.c.property_id == Property.id)
        .order_by(Property.name)
    )
    if not include_archived:
        stmt = stmt.where(Property.status == RecordStatus.ACTIVE)
    rows = (await db.execute(stmt)).all()
    return [
        PropertySummary(
            **PropertyOut.model_validate(p).model_dump(), room_count=rc, room_type_count=tc
        )
        for p, rc, tc in rows
    ]


@router.post("/properties", response_model=PropertyOut, status_code=status.HTTP_201_CREATED)
async def create_property(
    body: PropertyCreate, auth: CanManage, request: Request, db: DB
) -> Property:
    org = await db.get(Organisation, auth.organisation_id)
    assert org is not None
    prop = Property(
        organisation_id=org.id,
        name=body.name,
        slug=body.slug or slugify(body.name),
        property_type=body.property_type,
        timezone=body.timezone or org.default_timezone,
        currency=body.currency or org.default_currency,
        country_code=body.country_code or org.country_code,
        check_in_time=body.check_in_time,
        check_out_time=body.check_out_time,
        **body.model_dump(
            include={
                "address_line1",
                "address_line2",
                "city",
                "region",
                "postal_code",
                "phone",
                "email",
            }
        ),
    )
    db.add(prop)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise conflict_from_integrity(exc, PROPERTY_CONFLICTS) from None
    await audit.record(
        db,
        action="property.created",
        organisation_id=org.id,
        actor_user_id=auth.user.id,
        entity_type="property",
        entity_id=prop.id,
        data={"name": prop.name},
        ip_address=client_ip(request),
    )
    await db.refresh(prop)
    return prop


@router.get("/properties/{property_id}", response_model=PropertyOut)
async def read_property(property_id: uuid.UUID, auth: CanView, db: DB) -> Property:
    return await get_property(db, property_id)


@router.patch("/properties/{property_id}", response_model=PropertyOut)
async def update_property(
    property_id: uuid.UUID, body: PropertyUpdate, auth: CanManage, request: Request, db: DB
) -> Property:
    prop = await get_property(db, property_id)
    changes = body.model_dump(exclude_unset=True)
    for required in (
        "name",
        "property_type",
        "status",
        "timezone",
        "currency",
        "check_in_time",
        "check_out_time",
    ):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail=f"{required} cannot be empty.")
    diff = audit.apply_changes(prop, changes)
    if diff["after"]:
        await db.flush()
        await audit.record(
            db,
            action="property.updated",
            organisation_id=prop.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="property",
            entity_id=prop.id,
            data=diff,
            ip_address=client_ip(request),
        )
        await db.refresh(prop)
    return prop


# --- buildings --------------------------------------------------------------------------


@router.get("/properties/{property_id}/buildings", response_model=list[BuildingOut])
async def list_buildings(property_id: uuid.UUID, auth: CanView, db: DB) -> list[Building]:
    await get_property(db, property_id)
    rows = await db.scalars(
        select(Building)
        .where(Building.property_id == property_id)
        .order_by(Building.status, Building.sort_order, Building.name)
    )
    return list(rows.all())


@router.post(
    "/properties/{property_id}/buildings",
    response_model=BuildingOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_building(
    property_id: uuid.UUID, body: BuildingCreate, auth: CanManage, request: Request, db: DB
) -> Building:
    prop = await get_property(db, property_id)
    building = Building(
        organisation_id=prop.organisation_id, property_id=prop.id, **body.model_dump()
    )
    db.add(building)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError as exc:
        raise conflict_from_integrity(exc, BUILDING_CONFLICTS) from None
    await audit.record(
        db,
        action="building.created",
        organisation_id=prop.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="building",
        entity_id=building.id,
        data={"name": building.name, "property_id": str(prop.id)},
        ip_address=client_ip(request),
    )
    return building


@router.patch("/buildings/{building_id}", response_model=BuildingOut)
async def update_building(
    building_id: uuid.UUID, body: BuildingUpdate, auth: CanManage, request: Request, db: DB
) -> Building:
    building = await db.get(Building, building_id)
    if building is None:
        raise not_found("Building")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("name", "") is None or ("status" in changes and changes["status"] is None):
        raise HTTPException(status_code=422, detail="Name and status cannot be empty.")
    diff = audit.apply_changes(building, changes)
    if diff["after"]:
        try:
            async with db.begin_nested():
                await db.flush()
        except IntegrityError as exc:
            raise conflict_from_integrity(exc, BUILDING_CONFLICTS) from None
        await audit.record(
            db,
            action="building.updated",
            organisation_id=building.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="building",
            entity_id=building.id,
            data=diff,
            ip_address=client_ip(request),
        )
    return building
