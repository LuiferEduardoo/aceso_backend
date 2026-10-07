import mimetypes
from pathlib import Path
from typing import Any

from asyncer import asyncify


class LocalFileStorage:
    """Stores files under a base directory; keys are relative POSIX paths."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir.resolve()

    def _path(self, key: str) -> Path:
        path = (self._base_dir / key).resolve()
        if not path.is_relative_to(self._base_dir):
            raise ValueError(f"Invalid storage key: {key!r}")
        return path

    async def save(self, key: str, content: bytes) -> None:
        path = self._path(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncify(_write)()

    async def read(self, key: str) -> bytes | None:
        path = self._path(key)

        def _read() -> bytes | None:
            return path.read_bytes() if path.is_file() else None

        return await asyncify(_read)()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        await asyncify(path.unlink)(missing_ok=True)


class S3FileStorage:
    """Stores files in an S3-compatible bucket (e.g. Cloudflare R2); keys are object keys."""

    def __init__(self, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def save(self, key: str, content: bytes) -> None:
        content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        await asyncify(self._client.put_object)(
            Bucket=self._bucket, Key=key, Body=content, ContentType=content_type
        )

    async def read(self, key: str) -> bytes | None:
        def _read() -> bytes | None:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=key)
            except self._client.exceptions.NoSuchKey:
                return None
            return response["Body"].read()

        return await asyncify(_read)()

    async def delete(self, key: str) -> None:
        await asyncify(self._client.delete_object)(Bucket=self._bucket, Key=key)
