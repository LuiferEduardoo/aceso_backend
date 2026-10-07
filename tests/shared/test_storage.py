from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from aceso.shared.infrastructure.storage import LocalFileStorage, S3FileStorage


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


async def test_s3_save_read_and_delete() -> None:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="photos")
        storage = S3FileStorage(client, "photos")

        await storage.save("exercises/1/photo.jpg", b"data")
        head = client.head_object(Bucket="photos", Key="exercises/1/photo.jpg")
        assert head["ContentType"] == "image/jpeg"
        assert await storage.read("exercises/1/photo.jpg") == b"data"

        await storage.delete("exercises/1/photo.jpg")
        assert await storage.read("exercises/1/photo.jpg") is None
        await storage.delete("exercises/1/photo.jpg")  # idempotent
