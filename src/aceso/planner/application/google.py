from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aceso.planner.domain.entities import GoogleCalendar, GoogleCalendarLink, OAuthTokens
from aceso.planner.domain.errors import GoogleScopeNotGrantedError
from aceso.planner.domain.ports import (
    CalendarEventRepository,
    GoogleCalendarGateway,
    GoogleCalendarLinkRepository,
    OAuthStateSigner,
)
from aceso.shared.domain.credentials import CredentialStore, IntegrationProvider
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
REFRESH_MARGIN = timedelta(minutes=5)
PROVIDER = IntegrationProvider.GOOGLE


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def valid_google_tokens(
    gateway: GoogleCalendarGateway,
    credentials: CredentialStore,
    user_id: int,
    clock: Callable[[], datetime] = _utcnow,
) -> OAuthTokens:
    """Stored tokens, refreshed when about to expire. Google omits refresh_token on refresh."""
    payload = await credentials.get(user_id, PROVIDER)
    if payload is None:
        raise NotFoundError("Google account is not connected")
    tokens = OAuthTokens.from_payload(payload)
    if tokens.expires_within(clock(), REFRESH_MARGIN):
        if not tokens.refresh_token:
            raise InvalidOperationError("Google authorization expired; connect again")
        refreshed = await gateway.refresh(tokens.refresh_token)
        tokens = OAuthTokens(
            access_token=refreshed.access_token,
            expires_at=refreshed.expires_at,
            refresh_token=refreshed.refresh_token or tokens.refresh_token,
        )
        await credentials.save(user_id, PROVIDER, tokens.to_payload())
    return tokens


class StartGoogleAuthorization:
    def __init__(self, gateway: GoogleCalendarGateway, states: OAuthStateSigner) -> None:
        self._gateway = gateway
        self._states = states

    def execute(self, user_id: int) -> str:
        return self._gateway.authorization_url(self._states.issue(user_id))


class CompleteGoogleAuthorization:
    def __init__(
        self,
        gateway: GoogleCalendarGateway,
        states: OAuthStateSigner,
        credentials: CredentialStore,
        links: GoogleCalendarLinkRepository,
    ) -> None:
        self._gateway = gateway
        self._states = states
        self._credentials = credentials
        self._links = links

    async def execute(self, code: str, state: str, scope: str | None) -> int:
        user_id = self._states.verify(state)
        if scope is not None and CALENDAR_SCOPE not in scope.split():
            raise GoogleScopeNotGrantedError("Google Calendar access was not granted")
        tokens = await self._gateway.exchange_code(code)
        if not tokens.refresh_token:
            previous = await self._credentials.get(user_id, PROVIDER)
            kept = previous.get("refresh_token") if previous else None
            if not kept:
                raise InvalidOperationError(
                    "Google did not return a refresh token; remove the app access and retry"
                )
            tokens = OAuthTokens(tokens.access_token, tokens.expires_at, kept)
        await self._credentials.save(user_id, PROVIDER, tokens.to_payload())
        if await self._links.get(user_id) is None:
            await self._links.save(GoogleCalendarLink(user_id=user_id))
        return user_id


class ListGoogleCalendars:
    def __init__(
        self,
        gateway: GoogleCalendarGateway,
        credentials: CredentialStore,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._gateway = gateway
        self._credentials = credentials
        self._clock = clock

    async def execute(self, user_id: int) -> list[GoogleCalendar]:
        tokens = await valid_google_tokens(self._gateway, self._credentials, user_id, self._clock)
        return await self._gateway.list_calendars(tokens.access_token)


class SelectGoogleCalendar:
    """Point the sync at another calendar; local state is re-queued for the new target."""

    def __init__(
        self,
        gateway: GoogleCalendarGateway,
        credentials: CredentialStore,
        links: GoogleCalendarLinkRepository,
        events: CalendarEventRepository,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._calendars = ListGoogleCalendars(gateway, credentials, clock)
        self._links = links
        self._events = events

    async def execute(self, user_id: int, calendar_id: str) -> GoogleCalendarLink:
        link = await self._links.get(user_id)
        if link is None:
            raise NotFoundError("Google account is not connected")
        calendars = await self._calendars.execute(user_id)
        chosen = next(
            (
                c
                for c in calendars
                if c.id == calendar_id or (calendar_id == "primary" and c.primary)
            ),
            None,
        )
        if chosen is None:
            raise NotFoundError("Google calendar not found")
        if not chosen.writable:
            raise InvalidOperationError("That calendar is read-only; pick one you can edit")
        if chosen.id != link.calendar_id and not (chosen.primary and link.calendar_id == "primary"):
            link.calendar_id = chosen.id
            link.sync_token = None
            link.last_synced_at = None
            await self._events.reset_sync(user_id)
            link = await self._links.save(link)
        return link


class DisconnectGoogle:
    def __init__(self, credentials: CredentialStore, links: GoogleCalendarLinkRepository) -> None:
        self._credentials = credentials
        self._links = links

    async def execute(self, user_id: int) -> None:
        await self._credentials.delete(user_id, PROVIDER)
        await self._links.delete(user_id)


@dataclass(slots=True, frozen=True)
class GoogleConnectionStatus:
    connected: bool
    calendar_id: str | None = None
    last_synced_at: datetime | None = None


class GetGoogleStatus:
    """Whether the user connected Google and which calendar they sync. Never calls Google."""

    def __init__(self, credentials: CredentialStore, links: GoogleCalendarLinkRepository) -> None:
        self._credentials = credentials
        self._links = links

    async def execute(self, user_id: int) -> GoogleConnectionStatus:
        if await self._credentials.get(user_id, PROVIDER) is None:
            return GoogleConnectionStatus(connected=False)
        link = await self._links.get(user_id)
        if link is None:
            return GoogleConnectionStatus(connected=True)
        return GoogleConnectionStatus(
            connected=True, calendar_id=link.calendar_id, last_synced_at=link.last_synced_at
        )
