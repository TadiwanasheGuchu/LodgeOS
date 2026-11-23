"""Daily housekeeping list.

``GET /properties/{id}/housekeeping?date=`` works out what every room needs that day from
reservations and room status; ``POST .../housekeeping/{date}/rooms/{room_id}`` records a step.
Housekeeping staff do not have ``reservations.view``, so the list never names guests: it says
whether a guest is leaving, staying or arriving and how many people, nothing more.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import aliased

from app.core.errors import not_found
from app.modules.access.models import PermissionRecord, RolePermission, UserRole
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, AuthContext, client_ip, require_permission_anywhere
from app.modules.auth.models import User
from app.modules.auth.permissions import Permission
from app.modules.housekeeping.models import HousekeepingTask, TaskKind, TaskStatus
from app.modules.housekeeping.schemas import Assignee, Board, BoardRoom, TaskAction, TaskOut
from app.modules.maintenance.models import BlockStatus, RoomBlock
from app.modules.organisations.models import MembershipStatus, OrganisationUser
from app.modules.properties.models import Building, Property, RecordStatus
from app.modules.properties.router import get_property
from app.modules.reservations.models import (
    ReservationRoom,
    ReservationStatus,
    ReservationStatusChange,
)
from app.modules.rooms.models import HousekeepingStatus, Room, RoomType

router = APIRouter(prefix="/api/v1", tags=["housekeeping"])

CanView = Annotated[AuthContext, Depends(require_permission_anywhere(Permission.ROOMS_VIEW))]
CanWork = Annotated[
    AuthContext, Depends(require_permission_anywhere(Permission.ROOMS_HOUSEKEEPING))
]

S = ReservationStatus
FINISHED = (TaskStatus.DONE, TaskStatus.DECLINED)


def property_today(prop: Property) -> date:
    return datetime.now(ZoneInfo(prop.timezone)).date()


async def _assignees(db: DB, prop: Property) -> list[Assignee]:
    """Active members who can do housekeeping at this property."""
    rows = await db.execute(
        select(User.id, User.full_name)
        .join(OrganisationUser, OrganisationUser.user_id == User.id)
        .join(UserRole, UserRole.membership_id == OrganisationUser.id)
        .join(RolePermission, RolePermission.role_id == UserRole.role_id)
        .join(PermissionRecord, PermissionRecord.id == RolePermission.permission_id)
        .where(
            OrganisationUser.organisation_id == prop.organisation_id,
            OrganisationUser.status == MembershipStatus.ACTIVE,
            UserRole.organisation_id == prop.organisation_id,
            or_(UserRole.property_id.is_(None), UserRole.property_id == prop.id),
            PermissionRecord.code == Permission.ROOMS_HOUSEKEEPING.value,
        )
        .distinct()
        .order_by(User.full_name)
    )
    return [Assignee(user_id=r[0], name=r[1]) for r in rows.all()]


def _kind(
    room: Room, departing: bool, staying: bool, arriving: bool, arrival_in: bool
) -> TaskKind | None:
    if departing:
        return TaskKind.DEPARTURE
    if staying:
        return TaskKind.STAYOVER
    if arrival_in:  # the arriving guest is already in the room
        return None
    if room.housekeeping_status == HousekeepingStatus.DIRTY:
        return TaskKind.ARRIVAL if arriving else TaskKind.VACANT
    return None


async def _board(db: DB, prop: Property, day: date) -> Board:
    rooms = (
        await db.execute(
            select(Room, RoomType.code, Building.name)
            .join(RoomType, RoomType.id == Room.room_type_id)
            .outerjoin(Building, Building.id == Room.building_id)
            .where(Room.property_id == prop.id, Room.status == RecordStatus.ACTIVE)
            .order_by(Room.number)
        )
    ).all()
    stays = (
        await db.scalars(
            select(ReservationRoom).where(
                ReservationRoom.property_id == prop.id,
                ReservationRoom.room_id.is_not(None),
                ReservationRoom.check_in <= day,
                ReservationRoom.check_out >= day,
                ReservationRoom.status.in_(
                    (S.PROVISIONAL, S.CONFIRMED, S.CHECKED_IN, S.CHECKED_OUT)
                ),
            )
        )
    ).all()
    # Guests may leave before the booked departure date; the check-out time says when.
    zone = ZoneInfo(prop.timezone)
    left_on = {
        rid: at.astimezone(zone).date()
        for rid, at in (
            await db.execute(
                select(
                    ReservationStatusChange.reservation_id, ReservationStatusChange.changed_at
                ).where(
                    ReservationStatusChange.reservation_id.in_(
                        {s.reservation_id for s in stays if s.status == S.CHECKED_OUT}
                    ),
                    ReservationStatusChange.to_status == S.CHECKED_OUT,
                )
            )
        ).all()
    }

    def departs(s: ReservationRoom) -> date:
        if s.status == S.CHECKED_OUT and s.reservation_id in left_on:
            return min(s.check_out, left_on[s.reservation_id])
        return s.check_out

    blocked = set(
        (
            await db.scalars(
                select(RoomBlock.room_id).where(
                    RoomBlock.property_id == prop.id,
                    RoomBlock.status == BlockStatus.ACTIVE,
                    RoomBlock.start_date <= day,
                    RoomBlock.end_date > day,
                )
            )
        ).all()
    )
    assignee = aliased(User)
    finisher = aliased(User)
    tasks = {
        t.room_id: (t, a, f)
        for t, a, f in (
            await db.execute(
                select(HousekeepingTask, assignee.full_name, finisher.full_name)
                .outerjoin(assignee, assignee.id == HousekeepingTask.assigned_to)
                .outerjoin(finisher, finisher.id == HousekeepingTask.completed_by)
                .where(HousekeepingTask.property_id == prop.id, HousekeepingTask.task_date == day)
            )
        ).all()
    }

    out: list[BoardRoom] = []
    for room, type_code, building in rooms:
        mine = [s for s in stays if s.room_id == room.id]
        leaving = [
            s
            for s in mine
            if departs(s) == day and s.status in (S.CONFIRMED, S.CHECKED_IN, S.CHECKED_OUT)
        ]
        staying = [
            s
            for s in mine
            if s.check_in < day < s.check_out and s.status in (S.CONFIRMED, S.CHECKED_IN)
        ]
        arriving = [
            s
            for s in mine
            if s.check_in == day and s.status in (S.PROVISIONAL, S.CONFIRMED, S.CHECKED_IN)
        ]
        arrival_in = any(s.status == S.CHECKED_IN for s in arriving)
        kind = _kind(room, bool(leaving), bool(staying), bool(arriving), arrival_in)
        relevant = (leaving or staying or arriving)[:1]
        stored = tasks.get(room.id)
        task = None
        if stored is not None:
            t, assigned_name, finished_name = stored
            kind = kind or TaskKind(t.kind)
            task = TaskOut(
                status=t.status,
                kind=t.kind,
                assigned_to=t.assigned_to,
                assigned_to_name=assigned_name,
                note=t.note,
                started_at=t.started_at,
                completed_at=t.completed_at,
                completed_by_name=finished_name,
            )
        out.append(
            BoardRoom(
                room_id=room.id,
                number=room.number,
                floor=room.floor,
                building_name=building,
                room_type_code=type_code,
                housekeeping_status=room.housekeeping_status,
                maintenance_status=room.maintenance_status,
                blocked=room.id in blocked,
                kind=kind,
                departing=bool(leaving),
                guest_left=bool(leaving) and all(s.status == S.CHECKED_OUT for s in leaving),
                staying=bool(staying),
                arriving=bool(arriving),
                guests=sum(s.adults + s.children for s in relevant),
                task=task,
            )
        )
    return Board(
        date=day, today=property_today(prop), rooms=out, assignees=await _assignees(db, prop)
    )


@router.get("/properties/{property_id}/housekeeping", response_model=Board)
async def housekeeping_board(
    property_id: uuid.UUID,
    auth: CanView,
    db: DB,
    day: Annotated[date | None, Query(alias="date")] = None,
) -> Board:
    prop = await get_property(db, property_id, auth, Permission.ROOMS_VIEW)
    return await _board(db, prop, day or property_today(prop))


@router.post("/properties/{property_id}/housekeeping/{day}/rooms/{room_id}", response_model=Board)
async def housekeeping_step(
    property_id: uuid.UUID,
    day: date,
    room_id: uuid.UUID,
    body: TaskAction,
    auth: CanWork,
    request: Request,
    db: DB,
) -> Board:
    prop = await get_property(db, property_id, auth, Permission.ROOMS_HOUSEKEEPING)
    room = await db.get(Room, room_id, with_for_update=True)
    if room is None or room.property_id != prop.id:
        raise not_found("Room")
    today = property_today(prop)
    if day < today:
        raise HTTPException(status_code=409, detail="Past days cannot be changed.")
    if body.action != "assign" and day != today:
        raise HTTPException(status_code=409, detail="Rooms can only be worked on today.")

    board = await _board(db, prop, day)
    row = next(r for r in board.rooms if r.room_id == room.id)
    task = await db.scalar(
        select(HousekeepingTask)
        .where(HousekeepingTask.room_id == room.id, HousekeepingTask.task_date == day)
        .with_for_update()
    )
    if task is None:
        if row.kind is None:
            raise HTTPException(status_code=409, detail=f"Room {room.number} needs nothing today.")
        task = HousekeepingTask(
            organisation_id=prop.organisation_id,
            property_id=prop.id,
            room_id=room.id,
            task_date=day,
            kind=row.kind,
            status=TaskStatus.PENDING,
        )
        db.add(task)
    now = datetime.now(UTC)
    still_in = row.departing and not row.guest_left

    if body.action == "assign":
        if body.assigned_to is not None and body.assigned_to not in {
            a.user_id for a in board.assignees
        }:
            raise HTTPException(
                status_code=422, detail="Choose someone who does housekeeping here."
            )
        task.assigned_to = body.assigned_to
    elif body.action in ("start", "done"):
        if task.status in FINISHED:
            raise HTTPException(status_code=409, detail=f"Room {room.number} is already finished.")
        if still_in:
            raise HTTPException(
                status_code=409, detail=f"The guest in room {room.number} has not checked out yet."
            )
        task.assigned_to = task.assigned_to or auth.user.id
        task.started_at = task.started_at or now
        if body.action == "start":
            task.status = TaskStatus.IN_PROGRESS
        else:
            task.status = TaskStatus.DONE
            task.completed_at = now
            task.completed_by = auth.user.id
            task.note = body.note or task.note
            if room.housekeeping_status == HousekeepingStatus.DIRTY:
                room.housekeeping_status = HousekeepingStatus.CLEAN
                room.housekeeping_updated_at = now
                room.housekeeping_updated_by = auth.user.id
    elif body.action == "decline":
        if row.kind != TaskKind.STAYOVER:
            raise HTTPException(status_code=409, detail="Only a staying guest can decline service.")
        if task.status in FINISHED:
            raise HTTPException(status_code=409, detail=f"Room {room.number} is already finished.")
        if not (body.note and body.note.strip()):
            raise HTTPException(status_code=422, detail="Say why, for example do not disturb.")
        task.status = TaskStatus.DECLINED
        task.note = body.note.strip()
        task.completed_at = now
        task.completed_by = auth.user.id
    else:  # reopen
        if task.status not in FINISHED:
            raise HTTPException(status_code=409, detail=f"Room {room.number} is not finished.")
        task.status = TaskStatus.PENDING
        task.completed_at = None
        task.completed_by = None
        task.started_at = None
        task.note = body.note or None
        if room.housekeeping_status != HousekeepingStatus.DIRTY and task.kind != TaskKind.STAYOVER:
            room.housekeeping_status = HousekeepingStatus.DIRTY
            room.housekeeping_updated_at = now
            room.housekeeping_updated_by = auth.user.id

    await db.flush()
    await audit.record(
        db,
        action=f"housekeeping.{body.action}",
        organisation_id=prop.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="housekeeping_task",
        entity_id=task.id,
        data={"room": room.number, "date": str(day), "kind": task.kind, "status": task.status},
        ip_address=client_ip(request),
    )
    return await _board(db, prop, day)
