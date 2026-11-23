from typing import Annotated

from fastapi import Depends

from aceso.planner.application.habits import HabitService, HabitTracking
from aceso.planner.application.tasks import TaskService
from aceso.planner.infrastructure.habit_repository import SqlAlchemyHabitRepository
from aceso.planner.infrastructure.task_repository import SqlAlchemyTaskRepository
from aceso.shared.api.deps import SessionDep


def get_habit_service(session: SessionDep) -> HabitService:
    return HabitService(SqlAlchemyHabitRepository(session))


HabitServiceDep = Annotated[HabitService, Depends(get_habit_service)]


def get_habit_tracking(session: SessionDep) -> HabitTracking:
    return HabitTracking(SqlAlchemyHabitRepository(session))


HabitTrackingDep = Annotated[HabitTracking, Depends(get_habit_tracking)]


def get_task_service(session: SessionDep) -> TaskService:
    return TaskService(SqlAlchemyTaskRepository(session))


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
