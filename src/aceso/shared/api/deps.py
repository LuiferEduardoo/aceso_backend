from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.shared.config import Settings, get_settings
from aceso.shared.infrastructure.db import get_session

# scope="function" commits before the response is sent, so commit errors reach the client.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
SettingsDep = Annotated[Settings, Depends(get_settings)]
