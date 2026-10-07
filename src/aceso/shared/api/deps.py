from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.shared.config import Settings, get_settings
from aceso.shared.domain.storage import FileStorage
from aceso.shared.infrastructure.db import get_session
from aceso.shared.infrastructure.storage import LocalFileStorage

# scope="function" commits before the response is sent, so commit errors reach the client.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_file_storage(settings: SettingsDep) -> LocalFileStorage:
    return LocalFileStorage(settings.upload_dir)


FileStorageDep = Annotated[FileStorage, Depends(get_file_storage)]
