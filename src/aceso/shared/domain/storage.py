from typing import Protocol


class FileStorage(Protocol):
    """Port for binary file storage (local filesystem today, S3-compatible later)."""

    async def save(self, key: str, content: bytes) -> None: ...

    async def read(self, key: str) -> bytes | None: ...

    async def delete(self, key: str) -> None: ...
