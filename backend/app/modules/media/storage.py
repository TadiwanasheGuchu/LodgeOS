"""Object storage adapters (ADR-0014). Keys look like ``{org}/{asset}/{size}.webp``."""

import asyncio
from pathlib import Path
from typing import Any, Protocol

from app.core.config import Settings, get_settings


class StorageError(Exception):
    pass


class Storage(Protocol):
    name: str

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes | None: ...

    async def delete(self, key: str) -> None: ...


class LocalStorage:
    """A directory on disk; for development and single-server installs."""

    name = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise StorageError("Invalid storage key.")
        return path

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)

        await asyncio.to_thread(write)

    async def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return await asyncio.to_thread(lambda: path.read_bytes() if path.is_file() else None)

    async def delete(self, key: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(lambda: path.unlink(missing_ok=True))


class S3Storage:
    """Any S3-compatible service (AWS S3, Cloudflare R2, Wasabi, MinIO)."""

    name = "s3"

    def __init__(self, settings: Settings) -> None:
        import boto3

        self.bucket = settings.s3_bucket
        self.client: Any = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=(
                settings.s3_secret_access_key.get_secret_value()
                if settings.s3_secret_access_key
                else None
            ),
        )

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )

    async def get(self, key: str) -> bytes | None:
        from botocore.exceptions import ClientError

        def read() -> bytes | None:
            try:
                return bytes(self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read())
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                    return None
                raise

        return await asyncio.to_thread(read)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        settings = get_settings()
        _storage = (
            S3Storage(settings)
            if settings.storage_backend == "s3"
            else LocalStorage(settings.storage_local_path)
        )
    return _storage


def set_storage(storage: Storage | None) -> None:
    """For tests: use a specific store, or reset to the configured one."""
    global _storage
    _storage = storage
