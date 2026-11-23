import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Query, status
from fastapi.responses import RedirectResponse

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
    GoogleStatusRead,
    GoogleSyncResultRead,
)
from aceso.planner.application.google import (
    CompleteGoogleAuthorization,
    DisconnectGoogle,
    GetGoogleStatus,
    ListGoogleCalendars,
    SelectGoogleCalendar,
    StartGoogleAuthorization,
)
from aceso.planner.application.google_sync import SyncGoogleCalendar
from aceso.planner.domain.errors import GoogleScopeNotGrantedError
from aceso.shared.api.deps import CredentialStoreDep, SettingsDep
from aceso.shared.domain.errors import AuthenticationError, DomainError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner/google", tags=["planner"])

AGENDA_PATH = "/planner/agenda"


def _agenda_redirect(frontend_url: str, **params: str) -> RedirectResponse:
    """Send the browser back to the agenda; only fixed codes ever reach the query string."""
    url = f"{frontend_url.rstrip('/')}{AGENDA_PATH}?{urlencode(params)}"
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


def _failure_reason(exc: DomainError) -> str:
    if isinstance(exc, AuthenticationError):
        return "invalid_state"
    if isinstance(exc, GoogleScopeNotGrantedError):
        return "missing_scope"
    return "exchange_failed"


@router.get("/authorize", summary="URL to send the user to for Google Calendar consent")
async def google_authorize(
    user_id: CurrentUserIdDep, gateway: GoogleGatewayDep, states: GoogleStateSignerDep
) -> AuthorizationUrl:
    url = StartGoogleAuthorization(gateway, states).execute(user_id)
    return AuthorizationUrl(authorization_url=url)


@router.get(
    "/callback",
    summary="Google redirect target; the signed `state` identifies the user",
    description=(
        "Redirects (303) to `{FRONTEND_URL}/planner/agenda?google=connected`, or to "
        "`?google=error&reason=<code>` with `access_denied`, `authorization_failed`, "
        "`invalid_state`, `missing_scope` or `exchange_failed`."
    ),
    response_class=RedirectResponse,
    status_code=status.HTTP_303_SEE_OTHER,
)
async def google_callback(
    gateway: GoogleGatewayDep,
    states: GoogleStateSignerDep,
    credentials: CredentialStoreDep,
    links: GoogleLinkRepositoryDep,
    settings: SettingsDep,
    state: Annotated[str | None, Query()] = None,
    code: Annotated[str | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    frontend_url = settings.frontend_url
    if error:
        reason = "access_denied" if error == "access_denied" else "authorization_failed"
        return _agenda_redirect(frontend_url, google="error", reason=reason)
    if not state:
        return _agenda_redirect(frontend_url, google="error", reason="invalid_state")
    if not code:
        return _agenda_redirect(frontend_url, google="error", reason="authorization_failed")
    try:
        await CompleteGoogleAuthorization(gateway, states, credentials, links).execute(
            code, state, scope
        )
    except DomainError as exc:
        reason = _failure_reason(exc)
        logger.warning("Google authorization failed (%s): %s", reason, type(exc).__name__)
        return _agenda_redirect(frontend_url, google="error", reason=reason)
    return _agenda_redirect(frontend_url, google="connected")


@router.get("/status", summary="Whether Google is connected and which calendar is synced")
async def google_status(
    user_id: CurrentUserIdDep, credentials: CredentialStoreDep, links: GoogleLinkRepositoryDep
) -> GoogleStatusRead:
    result = await GetGoogleStatus(credentials, links).execute(user_id)
    return GoogleStatusRead.model_validate(result)


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
