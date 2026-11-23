"""Photos and logos (ADR-0014): only real images, metadata stripped, small sizes, S3-ready."""

import io
import uuid

import httpx
import pytest
from PIL import Image

from app.main import app
from app.modules.media.storage import LocalStorage, S3Storage, StorageError, set_storage
from app.modules.organisations.models import Role
from tests.conftest import csrf, login
from tests.test_reservations import _setup


@pytest.fixture(autouse=True)
def local_storage(tmp_path):
    set_storage(LocalStorage(str(tmp_path)))
    yield tmp_path
    set_storage(None)


def jpeg_with_gps(width=1200, height=800) -> bytes:
    img = Image.new("RGB", (width, height), (36, 121, 109))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0x0112] = 6  # Orientation: rotate 90° clockwise to display
    exif[0x8825] = {1: "S", 2: (22.0, 33.0, 0.0), 3: "E", 4: (17.0, 5.0, 0.0)}  # GPS
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    return buf.getvalue()


def png_logo() -> bytes:
    img = Image.new("RGBA", (600, 200), (0, 0, 0, 0))
    img.paste((18, 60, 53, 255), (50, 50, 550, 150))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


async def _upload(
    client, prop, data, *, kind="property_photo", content_type="image/jpeg", **params
):
    headers = {**(await csrf(client)), "Content-Type": content_type}
    return await client.post(
        f"/api/v1/properties/{prop['id']}/media",
        params={"kind": kind, **params},
        content=data,
        headers=headers,
    )


async def test_photo_is_resized_rotated_and_stripped_of_metadata(client, factory) -> None:
    _, prop, *_ = await _setup(client, factory)
    r = await _upload(client, prop, jpeg_with_gps(), alt_text="Chalet deck at sunset")
    assert r.status_code == 201, r.text
    photo = r.json()
    # Rotated by the EXIF orientation: 1200x800 becomes 800 wide before resizing.
    assert photo["widths"] == {"sm": 400, "md": 800, "lg": 800}
    served = await client.get(photo["urls"]["sm"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"
    assert served.headers["cache-control"] == "public, max-age=31536000, immutable"
    with Image.open(io.BytesIO(served.content)) as img:
        assert (img.format, img.width, img.height) == ("WEBP", 400, 600)
        assert len(img.getexif()) == 0  # no make, no GPS
    assert b"PhoneMaker" not in served.content


async def test_only_real_images_within_limits(client, factory) -> None:
    _, prop, *_ = await _setup(client, factory)
    r = await _upload(client, prop, b"<?php system($_GET['c']); ?>", alt_text="Not a photo")
    assert (r.status_code, r.json()["detail"]) == (
        422,
        "That file is not an image we can use. Upload a JPEG, PNG or WebP.",
    )
    gif = io.BytesIO()
    Image.new("RGB", (800, 600)).save(gif, "GIF")
    r = await _upload(client, prop, gif.getvalue(), content_type="image/gif", alt_text="A gif")
    assert r.json()["detail"] == "Upload a JPEG, PNG or WebP image."
    r = await _upload(client, prop, jpeg_with_gps(200, 150), alt_text="Too small")
    assert r.json()["detail"] == "Photos need to be at least 400 by 250 pixels."
    # A decompression bomb: tiny file, 100 megapixels.
    bomb = io.BytesIO()
    Image.new("1", (10_000, 10_000)).save(bomb, "PNG")
    assert len(bomb.getvalue()) < 100_000
    r = await _upload(client, prop, bomb.getvalue(), content_type="image/png", alt_text="Bomb")
    assert r.status_code == 422
    r = await _upload(client, prop, b"x" * (8 * 1024 * 1024 + 1), alt_text="Huge")
    assert r.status_code == 413
    r = await _upload(client, prop, jpeg_with_gps(), content_type="text/plain", alt_text="Text")
    assert r.status_code == 415
    r = await _upload(client, prop, jpeg_with_gps())
    assert r.status_code == 422 and "Describe the photo" in r.json()["detail"]


async def test_room_type_photos_logo_and_public_page(client, factory) -> None:
    org, prop, rt, _, _ = await _setup(client, factory)
    r = await _upload(client, prop, jpeg_with_gps(), kind="room_type_photo", alt_text="Tent")
    assert r.status_code == 422  # room type required
    room = await _upload(
        client,
        prop,
        jpeg_with_gps(),
        kind="room_type_photo",
        room_type_id=rt["id"],
        alt_text="Inside the tent",
    )
    assert room.status_code == 201
    first_logo = (
        await _upload(client, prop, png_logo(), kind="logo", content_type="image/png")
    ).json()
    assert first_logo["widths"] == {"sm": 160, "md": 480}
    with Image.open(io.BytesIO((await client.get(first_logo["urls"]["md"])).content)) as img:
        assert img.mode == "RGBA"  # transparency kept for logos
    # A new logo replaces the old one, and the old files are gone.
    second_logo = (
        await _upload(client, prop, png_logo(), kind="logo", content_type="image/png")
    ).json()
    assert (await client.get(first_logo["urls"]["md"])).status_code == 404
    listed = (await client.get(f"/api/v1/properties/{prop['id']}/media")).json()
    assert {m["id"] for m in listed} == {room.json()["id"], second_logo["id"]}

    headers = await csrf(client)
    await client.patch(
        f"/api/v1/properties/{prop['id']}",
        json={"booking_engine_enabled": True, "booking_terms": "Pay on arrival."},
        headers=headers,
    )
    public = (
        await httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t").get(
            f"/api/v1/public/properties/{org.slug}/{prop['slug']}"
        )
    ).json()
    assert public["logo"]["urls"] == second_logo["urls"]
    assert [p["alt"] for p in public["room_types"][0]["photos"]] == ["Inside the tent"]

    # Deleting removes the files.
    r = await client.delete(f"/api/v1/media/{room.json()['id']}", headers=headers)
    assert r.status_code == 204
    assert (await client.get(room.json()["urls"]["sm"])).status_code == 404


async def test_serving_accepts_only_ids_and_known_sizes(client, factory, local_storage) -> None:
    oid, aid = uuid.uuid4(), uuid.uuid4()
    assert (await client.get(f"/api/v1/media/{oid}/{aid}/xl.webp")).status_code == 422
    assert (await client.get(f"/api/v1/media/..%2F..%2Fetc/{aid}/sm.webp")).status_code in (
        404,
        422,
    )
    store = LocalStorage(str(local_storage))
    with pytest.raises(StorageError):
        await store.get("../../etc/passwd")


async def test_only_property_managers_upload(client, factory) -> None:
    org, prop, *_ = await _setup(client, factory)
    front = await factory.user()
    await factory.member(org, front, Role.RECEPTIONIST)
    await login(client, front.email)
    r = await _upload(client, prop, jpeg_with_gps(), alt_text="Deck")
    assert r.status_code == 403
    other = await factory.organisation("Elsewhere")
    stranger = await factory.user()
    await factory.member(other, stranger, Role.OWNER)
    await login(client, stranger.email)
    assert (await _upload(client, prop, jpeg_with_gps(), alt_text="Deck")).status_code == 404


def test_s3_adapter_against_moto_test_server() -> None:
    """The S3 adapter speaks real S3 HTTP to moto's S3-compatible server (a mock, not AWS)."""
    import asyncio

    import boto3
    from moto.server import ThreadedMotoServer

    from app.core.config import Settings

    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0)
    server.start()
    try:
        host, port = server.get_host_and_port()
        endpoint = f"http://{host}:{port}"
        settings = Settings(
            storage_backend="s3",
            s3_bucket="test-media",
            s3_endpoint_url=endpoint,
            s3_region="af-south-1",
            s3_access_key_id="test",
            s3_secret_access_key="test",
        )
        boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name="af-south-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        ).create_bucket(
            Bucket="test-media", CreateBucketConfiguration={"LocationConstraint": "af-south-1"}
        )
        store = S3Storage(settings)

        async def roundtrip() -> None:
            await store.put("org/asset/sm.webp", b"webp-bytes", "image/webp")
            assert await store.get("org/asset/sm.webp") == b"webp-bytes"
            await store.delete("org/asset/sm.webp")
            assert await store.get("org/asset/sm.webp") is None

        asyncio.run(roundtrip())
    finally:
        server.stop()
