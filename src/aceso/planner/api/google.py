from typing import Annotated

from fastapi import APIRouter, Query, status

from aceso.identity.api.deps import CurrentUserIdDep
from aceso.planner.api.deps import (
    CalendarEventRepositoryDep,
    GoogleGatewayDep,
    GoogleLinkRepositoryDep,
    GoogleStateSignerDep,
    HabitRepositoryDep,
    PlannerTimezoneDep,
    TaskRepositoryDep,
)
from aceso.planner.api.schemas import (
    AuthorizationUrl,
    GoogleCalendarLinkRead,
    GoogleCalendarRead,
    GoogleCalendarSelect,
    GoogleConnected,
    GoogleSyncResultRead,
)
from aceso.planner.application.google import (
    CompleteGoogleAuthorization,
    DisconnectGoogle,
    ListGoogleCalendars,
    SelectGoogleCalendar,
    StartGoogleAuthorization,
)
from aceso.planner.application.google_sync import SyncGoogleCalendar
from aceso.shared.api.deps import CredentialStoreDep
from aceso.shared.domain.errors import InvalidOperationError

router = APIRouter(prefix="/planner/google", tags=["planner"])


@router.get("/authorize", summary="URL to send the user to for Google Calendar consent")
async def google_authorize(
    user_id: CurrentUserIdDep, gateway: GoogleGatewayDep, states: GoogleStateSignerDep
) -> AuthorizationUrl:
    url = StartGoogleAuthorization(gateway, states).execute(user_id)
    return AuthorizationUrl(authorization_url=url)


@router.get("/callback", summary="Google redirect target; the signed `state` identifies the user")
async def google_callback(
    gateway: GoogleGatewayDep,
    states: GoogleStateSignerDep,
    credentials: CredentialStoreDep,
    links: GoogleLinkRepositoryDep,
    state: Annotated[str, Query()],
    code: Annotated[str | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> GoogleConnected:
    if error or not code:
        raise InvalidOperationError(f"Google authorization failed: {error or 'missing code'}")
    await CompleteGoogleAuthorization(gateway, states, credentials, links).execute(
        code, state, scope
    )
    return GoogleConnected()


@router.get("/calendars", summary="Calendars of the connected Google account")
async def google_calendars(
    user_id: CurrentUserIdDep, gateway: GoogleGatewayDep, credentials: CredentialStoreDep
) -> list[GoogleCalendarRead]:
    calendars = await ListGoogleCalendars(gateway, credentials).execute(user_id)
    return [GoogleCalendarRead.model_validate(c) for c in calendars]


@router.put("/calendar", summary="Choose the Google calendar to sync with")
async def select_google_calendar(
    payload: GoogleCalendarSelect,
    user_id: CurrentUserIdDep,
    gateway: GoogleGatewayDep,
    credentials: CredentialStoreDep,
    links: GoogleLinkRepositoryDep,
    events: CalendarEventRepositoryDep,
) -> GoogleCalendarLinkRead:
    link = await SelectGoogleCalendar(gateway, credentials, links, events).execute(
        user_id, payload.calendar_id
    )
    return GoogleCalendarLinkRead.model_validate(link)


@router.post("/sync", summary="Pull Google changes into the planner, then push local ones")
async def google_sync(
    user_id: CurrentUserIdDep,
    gateway: GoogleGatewayDep,
    credentials: CredentialStoreDep,
    links: GoogleLinkRepositoryDep,
    events: CalendarEventRepositoryDep,
    tasks: TaskRepositoryDep,
    habits: HabitRepositoryDep,
    tz: PlannerTimezoneDep,
) -> GoogleSyncResultRead:
    use_case = SyncGoogleCalendar(gateway, credentials, links, events, tasks, habits, tz=tz)
    result = await use_case.execute(user_id)
    return GoogleSyncResultRead.model_validate(result)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def google_disconnect(
    user_id: CurrentUserIdDep, credentials: CredentialStoreDep, links: GoogleLinkRepositoryDep
) -> None:
    await DisconnectGoogle(credentials, links).execute(user_id)
