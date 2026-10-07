from pathlib import Path

import pytest

from aceso.shared.infrastructure.storage import LocalFileStorage


async def test_save_read_and_delete(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    await storage.save("a/b/photo.jpg", b"data")
    assert (tmp_path / "a/b/photo.jpg").read_bytes() == b"data"
    assert await storage.read("a/b/photo.jpg") == b"data"
    await storage.delete("a/b/photo.jpg")
    assert await storage.read("a/b/photo.jpg") is None
    await storage.delete("a/b/photo.jpg")  # idempotent


async def test_rejects_keys_escaping_base_dir(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path / "uploads")
    with pytest.raises(ValueError):
        await storage.save("../outside.txt", b"x")
