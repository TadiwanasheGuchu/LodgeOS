"""Uploading and serving photos and logos (ADR-0014)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.core.errors import not_found
from app.modules.audit import service as audit
from app.modules.auth.deps import DB, Auth, client_ip
from app.modules.auth.permissions import Permission
from app.modules.media.images import MAX_BYTES, ImageRejected, process
from app.modules.media.models import MediaAsset, MediaKind
from app.modules.media.storage import get_storage
from app.modules.properties.router import get_property
from app.modules.rooms.models import RoomType

router = APIRouter(prefix="/api/v1", tags=["media"])
MAX_PROPERTY_PHOTOS = 30
MAX_ROOM_TYPE_PHOTOS = 10
Size = Literal["sm", "md", "lg"]


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: str
    room_type_id: uuid.UUID | None
    alt_text: str | None
    sort_order: int
    urls: dict[str, str]
    widths: dict[str, int]


class MediaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    alt_text: str | None = Field(default=None, min_length=3, max_length=200)
    sort_order: int | None = Field(default=None, ge=0, le=1000)


def media_url(asset: MediaAsset, size: str) -> str:
    return f"/api/v1/media/{asset.organisation_id}/{asset.id}/{size}.webp"


def media_out(asset: MediaAsset) -> MediaOut:
    return MediaOut(
        id=asset.id,
        kind=asset.kind,
        room_type_id=asset.room_type_id,
        alt_text=asset.alt_text,
        sort_order=asset.sort_order,
        urls={k: media_url(asset, k) for k in asset.variants},
        widths={k: int(v["width"]) for k, v in asset.variants.items()},
    )


def _key(asset: MediaAsset, size: str) -> str:
    return f"{asset.organisation_id}/{asset.id}/{size}.webp"


async def _remove_files(asset: MediaAsset) -> None:
    storage = get_storage()
    for size in asset.variants:
        await storage.delete(_key(asset, size))


async def _read_body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Images can be up to 8 MB.")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Images can be up to 8 MB.")
        chunks.append(chunk)
    if size == 0:
        raise HTTPException(status_code=422, detail="Choose an image to upload.")
    return b"".join(chunks)


@router.post(
    "/properties/{property_id}/media",
    response_model=MediaOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload(
    property_id: uuid.UUID,
    request: Request,
    auth: Auth,
    db: DB,
    kind: MediaKind,
    room_type_id: uuid.UUID | None = None,
    alt_text: Annotated[str | None, Query(max_length=200)] = None,
) -> MediaOut:
    prop = await get_property(db, property_id, auth, Permission.PROPERTIES_MANAGE)
    if not request.headers.get("content-type", "").startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG or WebP image.")
    alt = (alt_text or "").strip() or None
    if kind != MediaKind.LOGO and (alt is None or len(alt) < 3):
        raise HTTPException(
            status_code=422,
            detail="Describe the photo in a few words, for people who cannot see it.",
        )
    if kind == MediaKind.ROOM_TYPE_PHOTO:
        rt = await db.get(RoomType, room_type_id) if room_type_id else None
        if rt is None or rt.property_id != prop.id:
            raise HTTPException(status_code=422, detail="Choose a room type of this property.")
    elif room_type_id is not None:
        raise HTTPException(status_code=422, detail="Only room type photos belong to a room type.")

    live = (
        select(func.count())
        .select_from(MediaAsset)
        .where(MediaAsset.property_id == prop.id, MediaAsset.deleted_at.is_(None))
    )
    if kind == MediaKind.PROPERTY_PHOTO:
        count = await db.scalar(live.where(MediaAsset.kind == kind))
        if (count or 0) >= MAX_PROPERTY_PHOTOS:
            raise HTTPException(
                status_code=409, detail=f"A property can have {MAX_PROPERTY_PHOTOS} photos."
            )
    if kind == MediaKind.ROOM_TYPE_PHOTO:
        count = await db.scalar(live.where(MediaAsset.room_type_id == room_type_id))
        if (count or 0) >= MAX_ROOM_TYPE_PHOTOS:
            raise HTTPException(
                status_code=409, detail=f"A room type can have {MAX_ROOM_TYPE_PHOTOS} photos."
            )

    data = await _read_body(request)
    try:
        variants = process(data, logo=kind == MediaKind.LOGO)
    except ImageRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    storage = get_storage()
    asset = MediaAsset(
        id=uuid.uuid4(),
        organisation_id=prop.organisation_id,
        property_id=prop.id,
        room_type_id=room_type_id,
        kind=kind,
        alt_text=alt,
        sort_order=0,
        variants={
            v.name: {"width": v.width, "height": v.height, "bytes": len(v.data)} for v in variants
        },
        storage=storage.name,
        created_by=auth.user.id,
        created_at=datetime.now(UTC),
    )
    # Files first: a failed upload leaves no record; a failed commit leaves orphan files only.
    for v in variants:
        await storage.put(_key(asset, v.name), v.data, "image/webp")
    if kind == MediaKind.LOGO:
        for old in (
            await db.scalars(
                select(MediaAsset).where(
                    MediaAsset.property_id == prop.id,
                    MediaAsset.kind == MediaKind.LOGO,
                    MediaAsset.deleted_at.is_(None),
                )
            )
        ).all():
            old.deleted_at = datetime.now(UTC)
            await _remove_files(old)
    else:
        top = await db.scalar(
            select(func.max(MediaAsset.sort_order)).where(
                MediaAsset.property_id == prop.id,
                MediaAsset.kind == kind,
                MediaAsset.room_type_id.is_(None)
                if room_type_id is None
                else MediaAsset.room_type_id == room_type_id,
                MediaAsset.deleted_at.is_(None),
            )
        )
        asset.sort_order = (top or 0) + 1 if top is not None else 0
    db.add(asset)
    await db.flush()
    await audit.record(
        db,
        action="media.uploaded",
        organisation_id=prop.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="media_asset",
        entity_id=asset.id,
        data={"kind": kind.value, "bytes": len(data)},
        ip_address=client_ip(request),
    )
    return media_out(asset)


@router.get("/properties/{property_id}/media", response_model=list[MediaOut])
async def list_media(property_id: uuid.UUID, auth: Auth, db: DB) -> list[MediaOut]:
    prop = await get_property(db, property_id, auth, Permission.PROPERTIES_VIEW)
    rows = await db.scalars(
        select(MediaAsset)
        .where(MediaAsset.property_id == prop.id, MediaAsset.deleted_at.is_(None))
        .order_by(
            MediaAsset.kind, MediaAsset.room_type_id, MediaAsset.sort_order, MediaAsset.created_at
        )
    )
    return [media_out(a) for a in rows.all()]


async def _asset(db: DB, auth: Auth, asset_id: uuid.UUID) -> MediaAsset:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise not_found("Photo")
    auth.require_for_property(Permission.PROPERTIES_MANAGE, asset.property_id)
    return asset


@router.patch("/media/{asset_id}", response_model=MediaOut)
async def update_media(asset_id: uuid.UUID, body: MediaUpdate, auth: Auth, db: DB) -> MediaOut:
    asset = await _asset(db, auth, asset_id)
    changes = body.model_dump(exclude_unset=True)
    if "alt_text" in changes and changes["alt_text"] is None and asset.kind != MediaKind.LOGO:
        raise HTTPException(status_code=422, detail="Photos need a description.")
    for k, v in changes.items():
        setattr(asset, k, v)
    await db.flush()
    return media_out(asset)


@router.delete("/media/{asset_id}", status_code=204)
async def delete_media(asset_id: uuid.UUID, auth: Auth, request: Request, db: DB) -> None:
    asset = await _asset(db, auth, asset_id)
    asset.deleted_at = datetime.now(UTC)
    await db.flush()
    await _remove_files(asset)
    await audit.record(
        db,
        action="media.deleted",
        organisation_id=asset.organisation_id,
        actor_user_id=auth.user.id,
        entity_type="media_asset",
        entity_id=asset.id,
        data={"kind": asset.kind},
        ip_address=client_ip(request),
    )


@router.get("/media/{organisation_id}/{asset_id}/{size}.webp", include_in_schema=False)
async def serve(organisation_id: uuid.UUID, asset_id: uuid.UUID, size: Size) -> Response:
    """Public: photos are marketing content. Only UUIDs and known sizes reach storage."""
    data = await get_storage().get(f"{organisation_id}/{asset_id}/{size}.webp")
    if data is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return Response(
        content=data,
        media_type="image/webp",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
