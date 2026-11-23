"""Room blocks are checked under the same room-type lock as bookings, so a block can never
oversell a room type and a booking can never land on a blocked night."""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.maintenance.models import BlockStatus, RoomBlock
from app.modules.reservations.models import Reservation, ReservationRoom
from app.modules.reservations.service import ASSIGNABLE, BookingError, availability
from app.modules.rooms.models import MaintenanceStatus, Room, RoomType


async def create_block(
    db: AsyncSession,
    *,
    room: Room,
    start_date: date,
    end_date: date,
    reason: str,
    ticket_id: uuid.UUID | None,
    user_id: uuid.UUID,
) -> RoomBlock:
    if end_date <= start_date:
        raise BookingError("The room must come back on a later date than it goes out.", 422)
    # Same lock as bookings: nothing can be sold for this room type while we check.
    room_type = await db.scalar(
        select(RoomType).where(RoomType.id == room.room_type_id).with_for_update()
    )
    assert room_type is not None

    overlapping_block = await db.scalar(
        select(func.count())
        .select_from(RoomBlock)
        .where(
            RoomBlock.room_id == room.id,
            RoomBlock.status == BlockStatus.ACTIVE,
            RoomBlock.start_date < end_date,
            RoomBlock.end_date > start_date,
        )
    )
    if overlapping_block:
        raise BookingError(f"Room {room.number} is already blocked on some of these nights.")

    guests = (
        await db.scalars(
            select(Reservation.reference)
            .join(ReservationRoom, ReservationRoom.reservation_id == Reservation.id)
            .where(
                ReservationRoom.room_id == room.id,
                ReservationRoom.status.in_(ASSIGNABLE),
                ReservationRoom.check_in < end_date,
                ReservationRoom.check_out > start_date,
            )
        )
    ).all()
    if guests:
        raise BookingError(
            f"Room {room.number} has guests on these nights ({', '.join(sorted(guests))}). "
            "Move them to another room first."
        )

    # The room is only part of sellable inventory if it is active and not out of order.
    if room.status == "active" and room.maintenance_status != MaintenanceStatus.OUT_OF_ORDER:
        for night in await availability(db, room_type.id, start_date, end_date):
            if night.free < 1:
                raise BookingError(
                    f"Blocking room {room.number} would oversell {room_type.name} on "
                    f"{night.night.isoformat()}. Move or cancel a booking first."
                )

    block = RoomBlock(
        organisation_id=room.organisation_id,
        property_id=room.property_id,
        room_id=room.id,
        ticket_id=ticket_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status=BlockStatus.ACTIVE,
        created_by=user_id,
    )
    db.add(block)
    await db.flush()
    return block
