from typing import Annotated

from fastapi import Depends

from aceso.planner.application.habits import HabitService, HabitTracking
from aceso.planner.infrastructure.habit_repository import SqlAlchemyHabitRepository
from aceso.shared.api.deps import SessionDep


def get_habit_service(session: SessionDep) -> HabitService:
    return HabitService(SqlAlchemyHabitRepository(session))


HabitServiceDep = Annotated[HabitService, Depends(get_habit_service)]


def get_habit_tracking(session: SessionDep) -> HabitTracking:
    return HabitTracking(SqlAlchemyHabitRepository(session))


HabitTrackingDep = Annotated[HabitTracking, Depends(get_habit_tracking)]
