from typing import Annotated

from fastapi import Depends

from aceso.health.domain.ports import HealthProvider
from aceso.health.infrastructure.garmin import GarminHealthProvider
from aceso.health.infrastructure.repository import SqlAlchemyHealthRepository
from aceso.shared.api.deps import SessionDep


def get_health_repository(session: SessionDep) -> SqlAlchemyHealthRepository:
    return SqlAlchemyHealthRepository(session)


HealthRepositoryDep = Annotated[SqlAlchemyHealthRepository, Depends(get_health_repository)]


def get_garmin_provider() -> HealthProvider:
    return GarminHealthProvider()


GarminProviderDep = Annotated[HealthProvider, Depends(get_garmin_provider)]
