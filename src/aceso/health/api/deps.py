from typing import Annotated

from fastapi import Depends

from aceso.health.infrastructure.repository import SqlAlchemyHealthRepository
from aceso.shared.api.deps import SessionDep


def get_health_repository(session: SessionDep) -> SqlAlchemyHealthRepository:
    return SqlAlchemyHealthRepository(session)


HealthRepositoryDep = Annotated[SqlAlchemyHealthRepository, Depends(get_health_repository)]
