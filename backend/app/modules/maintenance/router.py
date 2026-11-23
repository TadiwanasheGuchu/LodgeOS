"""Maintenance tickets and room blocks.

Anyone who can see rooms may report a problem (housekeeping finds most of them). Working on
tickets and taking rooms out of sale needs ``rooms.maintenance_update``.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.core.errors import not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission_anywhere
from app.modules.auth.models import User
from app.modules.auth.permissions import Permission
from app.modules.maintenance import service
from app.modules.maintenance.models import (
    BlockStatus,
    MaintenanceTicket,
    RoomBlock,
    TicketStatus,
)
from app.modules.maintenance.schemas import (
    BlockCreate,
    BlockOut,
    TicketCreate,
    TicketOut,
    TicketUpdate,
)
from app.modules.organisations.models import MembershipStatus, OrganisationUser
from app.modules.properties.router import get_property
from app.modules.reservations.service import BookingError
from app.modules.rooms.models import Room

router = APIRouter(prefix="/api/v1", tags=["maintenance"])

CanView = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.ROOMS_VIEW))]
CanWork = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.ROOMS_MAINTENANCE))]
CLOSED = (TicketStatus.RESOLVED, TicketStatus.CANCELLED)


async def _ticket_out(db: DB, t: MaintenanceTicket) -> TicketOut:
    reporter = aliased(User)
    assignee = aliased(User)
    row = (
        await db.execute(
            select(reporter.full_name, assignee.full_name, Room.number)
            .select_from(MaintenanceTicket)
            .join(reporter, reporter.id == MaintenanceTicket.reported_by)
            .outerjoin(assignee, assignee.id == MaintenanceTicket.assigned_to)
            .outerjoin(Room, Room.id == MaintenanceTicket.room_id)
            .where(MaintenanceTicket.id == t.id)
        )
    ).one()
    blocks = (
        await db.scalars(
            select(RoomBlock).where(RoomBlock.ticket_id == t.id).order_by(RoomBlock.start_date)
        )
    ).all()
    return TicketOut(
        id=t.id,
        property_id=t.property_id,
        room_id=t.room_id,
        room_number=row[2],
        location=t.location,
        title=t.title,
        description=t.description,
        priority=t.priority,
        status=t.status,
        reported_by_name=row[0],
        assigned_to=t.assigned_to,
        assigned_to_name=row[1],
        resolution=t.resolution,
        created_at=t.created_at,
        closed_at=t.closed_at,
        blocks=[BlockOut.model_validate(b) for b in blocks],
    )


async def _ticket(
    db: DB, auth: AuthContext, ticket_id: uuid.UUID, perm: Permission
) -> MaintenanceTicket:
    t = await db.get(MaintenanceTicket, ticket_id)
    if t is None:
        raise not_found("Ticket")
    auth.require_for_property(perm, t.property_id)
    return t


def _booking_error(exc: BookingError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


@router.get("/properties/{property_id}/maintenance/tickets", response_model=list[TicketOut])
async def list_tickets(
    property_id: uuid.UUID,
    auth: CanView,
    db: DB,
    closed: bool = False,
) -> list[TicketOut]:
    prop = await get_property(db, property_id, auth, Permission.ROOMS_VIEW)
    stmt = select(MaintenanceTicket).where(MaintenanceTicket.property_id == prop.id)
    stmt = stmt.where(
        MaintenanceTicket.status.in_(CLOSED) if closed else MaintenanceTicket.status.not_in(CLOSED)
    )
    # Urgent first, then oldest first: the order a technician should work in.
    order = {"urgent": 0, "normal": 1, "low": 2}
    tickets = sorted(
        (await db.scalars(stmt.order_by(MaintenanceTicket.created_at))).all(),
        key=lambda t: (order.get(t.priority, 9), t.created_at),
    )
    return [await _ticket_out(db, t) for t in tickets[:200]]


@router.post(
    "/properties/{property_id}/maintenance/tickets",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
)
async def report_problem(
    property_id: uuid.UUID, body: TicketCreate, auth: CanView, request: Request, db: DB
) -> TicketOut:
    prop = await get_property(db, property_id, auth, Permission.ROOMS_VIEW)
    if body.room_id is not None:
        room = await db.get(Room, body.room_id)
        if room is None or room.property_id != prop.id:
            raise HTTPException(status_code=422, detail="Choose a room of this property.")
    ticket = MaintenanceTicket(
        organisation_id=prop.organisation_id,
        property_id=prop.id,
        reported_by=auth.user.id,
        **body.model_dump(),
    )
    db.add(ticket)
    await db.flush()
    await audit.record(
        db,
        action="maintenance.reported",
        organisation_id=prop.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="maintenance_ticket",
        entity_id=ticket.id,
        data={"title": ticket.title, "priority": ticket.priority},
        ip_address=client_ip(request),
    )
    return await _ticket_out(db, ticket)


@router.patch("/maintenance/tickets/{ticket_id}", response_model=TicketOut)
async def update_ticket(
    ticket_id: uuid.UUID, body: TicketUpdate, auth: CanWork, request: Request, db: DB
) -> TicketOut:
    ticket = await _ticket(db, auth, ticket_id, Permission.ROOMS_MAINTENANCE)
    if ticket.status in CLOSED:
        raise HTTPException(status_code=409, detail="This ticket is closed.")
    changes = body.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is None:
        raise HTTPException(status_code=422, detail="Status cannot be empty.")
    if "priority" in changes and changes["priority"] is None:
        raise HTTPException(status_code=422, detail="Priority cannot be empty.")
    if changes.get("assigned_to") is not None:
        member = await db.scalar(
            select(OrganisationUser.id).where(
                OrganisationUser.user_id == changes["assigned_to"],
                OrganisationUser.organisation_id == ticket.organisation_id,
                OrganisationUser.status == MembershipStatus.ACTIVE,
            )
        )
        if member is None:
            raise HTTPException(status_code=422, detail="Choose an active member of the team.")
    closing = changes.get("status") in CLOSED
    if changes.get("status") == TicketStatus.RESOLVED and not (
        changes.get("resolution") or ticket.resolution
    ):
        raise HTTPException(status_code=422, detail="Say briefly what was done.")
    diff = audit.apply_changes(ticket, changes)
    released = 0
    if closing:
        ticket.closed_at = datetime.now(UTC)
        # A fixed problem gives its rooms back: release this ticket's remaining blocks.
        for block in (
            await db.scalars(
                select(RoomBlock).where(
                    RoomBlock.ticket_id == ticket.id, RoomBlock.status == BlockStatus.ACTIVE
                )
            )
        ).all():
            block.status = BlockStatus.RELEASED
            released += 1
    await db.flush()
    if diff["after"]:
        await audit.record(
            db,
            action="maintenance.updated",
            organisation_id=ticket.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="maintenance_ticket",
            entity_id=ticket.id,
            data={**diff, "blocks_released": released},
            ip_address=client_ip(request),
        )
    return await _ticket_out(db, ticket)


@router.post(
    "/maintenance/tickets/{ticket_id}/blocks",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
)
async def block_room(
    ticket_id: uuid.UUID, body: BlockCreate, auth: CanWork, request: Request, db: DB
) -> TicketOut:
    ticket = await _ticket(db, auth, ticket_id, Permission.ROOMS_MAINTENANCE)
    if ticket.status in CLOSED:
        raise HTTPException(status_code=409, detail="This ticket is closed.")
    if ticket.room_id is None:
        raise HTTPException(status_code=422, detail="Only tickets for a room can block it.")
    room = await db.get(Room, ticket.room_id)
    assert room is not None
    try:
        block = await service.create_block(
            db,
            room=room,
            start_date=body.start_date,
            end_date=body.end_date,
            reason=ticket.title,
            ticket_id=ticket.id,
            user_id=auth.user.id,
        )
    except BookingError as exc:
        raise _booking_error(exc) from None
    await audit.record(
        db,
        action="maintenance.room_blocked",
        organisation_id=ticket.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="room_block",
        entity_id=block.id,
        data={"room": room.number, "from": str(block.start_date), "to": str(block.end_date)},
        ip_address=client_ip(request),
    )
    return await _ticket_out(db, ticket)


@router.post("/room-blocks/{block_id}/release", response_model=BlockOut)
async def release_block(block_id: uuid.UUID, auth: CanWork, request: Request, db: DB) -> RoomBlock:
    block = await db.get(RoomBlock, block_id)
    if block is None:
        raise not_found("Room block")
    auth.require_for_property(Permission.ROOMS_MAINTENANCE, block.property_id)
    if block.status == BlockStatus.ACTIVE:
        block.status = BlockStatus.RELEASED
        await db.flush()
        await audit.record(
            db,
            action="maintenance.room_released",
            organisation_id=block.organisation_id,
            actor_user_id=auth.user.id,
            entity_type="room_block",
            entity_id=block.id,
            data={"from": str(block.start_date), "to": str(block.end_date)},
            ip_address=client_ip(request),
        )
    return block


@router.get("/properties/{property_id}/room-blocks", response_model=list[BlockOut])
async def list_blocks(
    property_id: uuid.UUID,
    auth: CanView,
    db: DB,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> list[RoomBlock]:
    prop = await get_property(db, property_id, auth, Permission.ROOMS_VIEW)
    rows = await db.scalars(
        select(RoomBlock)
        .where(
            RoomBlock.property_id == prop.id,
            RoomBlock.status == BlockStatus.ACTIVE,
            RoomBlock.start_date < date_to,
            RoomBlock.end_date > date_from,
        )
        .order_by(RoomBlock.start_date)
    )
    return list(rows.all())
