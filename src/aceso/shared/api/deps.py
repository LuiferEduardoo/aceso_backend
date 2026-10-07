from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.shared.config import Settings, get_settings
from aceso.shared.domain.credentials import CredentialStore
from aceso.shared.domain.storage import FileStorage
from aceso.shared.infrastructure.credentials import SqlAlchemyCredentialStore
from aceso.shared.infrastructure.crypto import FernetCipher
from aceso.shared.infrastructure.db import get_session
from aceso.shared.infrastructure.storage import LocalFileStorage

# scope="function" commits before the response is sent, so commit errors reach the client.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_file_storage(settings: SettingsDep) -> LocalFileStorage:
    return LocalFileStorage(settings.upload_dir)


FileStorageDep = Annotated[FileStorage, Depends(get_file_storage)]


def get_credential_store(session: SessionDep, settings: SettingsDep) -> SqlAlchemyCredentialStore:
    return SqlAlchemyCredentialStore(session, FernetCipher(settings.fernet_key))


CredentialStoreDep = Annotated[CredentialStore, Depends(get_credential_store)]
