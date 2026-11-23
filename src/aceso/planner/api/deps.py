from typing import Annotated

from fastapi import Depends

from aceso.planner.application.agenda import Agenda
from aceso.planner.application.calendar import CalendarService
from aceso.planner.application.habits import HabitService, HabitTracking
from aceso.planner.application.tasks import TaskService
from aceso.planner.infrastructure.event_repository import SqlAlchemyCalendarEventRepository
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
    return TaskService(
        SqlAlchemyTaskRepository(session), SqlAlchemyCalendarEventRepository(session)
    )


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


def get_calendar_service(session: SessionDep) -> CalendarService:
    return CalendarService(SqlAlchemyCalendarEventRepository(session))


CalendarServiceDep = Annotated[CalendarService, Depends(get_calendar_service)]


def get_agenda(session: SessionDep) -> Agenda:
    return Agenda(
        SqlAlchemyCalendarEventRepository(session),
        SqlAlchemyTaskRepository(session),
        SqlAlchemyHabitRepository(session),
    )


AgendaDep = Annotated[Agenda, Depends(get_agenda)]
