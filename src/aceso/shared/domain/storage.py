from typing import Protocol


class FileStorage(Protocol):
    """Port for binary file storage (local filesystem or S3-compatible such as Cloudflare R2)."""

    async def save(self, key: str, content: bytes) -> None: ...

    async def read(self, key: str) -> bytes | None: ...

    async def delete(self, key: str) -> None: ...
