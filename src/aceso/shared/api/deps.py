from functools import lru_cache
from typing import Annotated, Any

import boto3
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.shared.config import Settings, get_settings
from aceso.shared.domain.credentials import CredentialStore
from aceso.shared.domain.storage import FileStorage
from aceso.shared.infrastructure.credentials import SqlAlchemyCredentialStore
from aceso.shared.infrastructure.crypto import FernetCipher
from aceso.shared.infrastructure.db import get_session
from aceso.shared.infrastructure.storage import LocalFileStorage, S3FileStorage

# scope="function" commits before the response is sent, so commit errors reach the client.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def _s3_client(endpoint_url: str, access_key_id: str, secret_access_key: str, region: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region,
    )


def get_file_storage(settings: SettingsDep) -> FileStorage:
    if settings.storage_backend == "s3":
        client = _s3_client(
            settings.s3_endpoint_url,
            settings.s3_access_key_id,
            settings.s3_secret_access_key,
            settings.s3_region,
        )
        return S3FileStorage(client, settings.s3_bucket)
    return LocalFileStorage(settings.upload_dir)


FileStorageDep = Annotated[FileStorage, Depends(get_file_storage)]


def get_credential_store(session: SessionDep, settings: SettingsDep) -> SqlAlchemyCredentialStore:
    return SqlAlchemyCredentialStore(session, FernetCipher(settings.fernet_key))


CredentialStoreDep = Annotated[CredentialStore, Depends(get_credential_store)]
