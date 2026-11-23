from typing import Annotated

from fastapi import Depends

from aceso.identity.api.deps import JwtServiceDep
from aceso.planner.application.agenda import Agenda
from aceso.planner.application.calendar import CalendarService
from aceso.planner.application.habits import HabitService, HabitTracking
from aceso.planner.application.tasks import TaskService
from aceso.planner.domain.ports import (
    CalendarEventRepository,
    GoogleCalendarGateway,
    GoogleCalendarLinkRepository,
    HabitRepository,
    OAuthStateSigner,
    TaskRepository,
)
from aceso.planner.infrastructure.event_repository import SqlAlchemyCalendarEventRepository
from aceso.planner.infrastructure.google_calendar import GoogleCalendarClient
from aceso.planner.infrastructure.google_link_repository import (
    SqlAlchemyGoogleCalendarLinkRepository,
)
from aceso.planner.infrastructure.habit_repository import SqlAlchemyHabitRepository
from aceso.planner.infrastructure.task_repository import SqlAlchemyTaskRepository
from aceso.shared.api.deps import SessionDep, SettingsDep
from aceso.shared.infrastructure.oauth_state import JwtOAuthStateSigner

GOOGLE_STATE_PURPOSE = "google_oauth_state"


def get_habit_service(session: SessionDep) -> HabitService:
    return HabitService(
        SqlAlchemyHabitRepository(session), SqlAlchemyCalendarEventRepository(session)
    )


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


def get_calendar_event_repository(session: SessionDep) -> CalendarEventRepository:
    return SqlAlchemyCalendarEventRepository(session)


CalendarEventRepositoryDep = Annotated[
    CalendarEventRepository, Depends(get_calendar_event_repository)
]


def get_google_gateway(settings: SettingsDep) -> GoogleCalendarGateway:
    return GoogleCalendarClient(
        settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri
    )


GoogleGatewayDep = Annotated[GoogleCalendarGateway, Depends(get_google_gateway)]


def get_google_state_signer(jwt_service: JwtServiceDep) -> OAuthStateSigner:
    return JwtOAuthStateSigner(jwt_service, GOOGLE_STATE_PURPOSE)


GoogleStateSignerDep = Annotated[OAuthStateSigner, Depends(get_google_state_signer)]


def get_google_link_repository(session: SessionDep) -> GoogleCalendarLinkRepository:
    return SqlAlchemyGoogleCalendarLinkRepository(session)


GoogleLinkRepositoryDep = Annotated[
    GoogleCalendarLinkRepository, Depends(get_google_link_repository)
]


def get_task_repository(session: SessionDep) -> TaskRepository:
    return SqlAlchemyTaskRepository(session)


TaskRepositoryDep = Annotated[TaskRepository, Depends(get_task_repository)]


def get_habit_repository(session: SessionDep) -> HabitRepository:
    return SqlAlchemyHabitRepository(session)


HabitRepositoryDep = Annotated[HabitRepository, Depends(get_habit_repository)]
