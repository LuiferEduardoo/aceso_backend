from datetime import UTC, datetime, timedelta

import pytest

from aceso.planner.application.google import (
    CompleteGoogleAuthorization,
    GetGoogleStatus,
    GoogleConnectionStatus,
    ListGoogleCalendars,
    SelectGoogleCalendar,
    valid_google_tokens,
)
from aceso.planner.domain.entities import (
    CalendarEvent,
    EventSource,
    GoogleCalendarLink,
    OAuthTokens,
)
from aceso.planner.domain.errors import GoogleScopeNotGrantedError
from aceso.planner.infrastructure.google_calendar import GoogleCalendarClient
from aceso.shared.domain.credentials import IntegrationProvider
from aceso.shared.domain.errors import (
    AuthenticationError,
    IntegrationError,
    InvalidOperationError,
    NotFoundError,
)
from tests.planner.fakes import (
    FakeCalendarEventRepository,
    FakeCredentialStore,
    FakeGoogleCalendarLinkRepository,
    FakeStates,
)
from tests.planner.google_mock import FakeGoogleCalendarApi

GOOGLE = IntegrationProvider.GOOGLE
SCOPE = "email https://www.googleapis.com/auth/calendar"


def _client(api: FakeGoogleCalendarApi) -> GoogleCalendarClient:
    return GoogleCalendarClient("cid", "secret", "http://localhost/cb", transport=api.transport())


def _payload(expires_in: timedelta, refresh_token: str | None = "refresh-0") -> dict:
    return OAuthTokens("access-0", datetime.now(UTC) + expires_in, refresh_token).to_payload()


def test_authorization_url_asks_for_offline_calendar_access() -> None:
    url = _client(FakeGoogleCalendarApi()).authorization_url("abc")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    for part in ("state=abc", "access_type=offline", "prompt=consent", "client_id=cid"):
        assert part in url
    assert "auth%2Fcalendar" in url


def test_unconfigured_client_fails_clearly() -> None:
    with pytest.raises(IntegrationError):
        GoogleCalendarClient("", "", "http://localhost/cb").authorization_url("abc")


async def test_complete_authorization_stores_tokens_and_link() -> None:
    api, store, links = (
        FakeGoogleCalendarApi(),
        FakeCredentialStore(),
        FakeGoogleCalendarLinkRepository(),
    )
    use_case = CompleteGoogleAuthorization(_client(api), FakeStates(), store, links)

    assert await use_case.execute("code-1", "state-7", SCOPE) == 7

    assert store.data[(7, GOOGLE)]["refresh_token"] == "refresh-1"
    assert links.links[7].calendar_id == "primary"
    assert api.token_grants == ["authorization_code"]


async def test_reconnect_without_refresh_token_keeps_previous_one() -> None:
    api = FakeGoogleCalendarApi(refresh_token_on_exchange=False)
    store, links = FakeCredentialStore(), FakeGoogleCalendarLinkRepository()
    use_case = CompleteGoogleAuthorization(_client(api), FakeStates(), store, links)
    with pytest.raises(InvalidOperationError):
        await use_case.execute("code", "state-1", None)

    await store.save(1, GOOGLE, _payload(timedelta(minutes=-5), "refresh-old"))
    await links.save(GoogleCalendarLink(user_id=1, calendar_id="family", sync_token="t"))
    await use_case.execute("code", "state-1", None)
    assert store.data[(1, GOOGLE)]["refresh_token"] == "refresh-old"
    assert links.links[1].calendar_id == "family"  # an existing link is kept


async def test_complete_authorization_rejects_bad_state_scope_and_code() -> None:
    use_case = CompleteGoogleAuthorization(
        _client(FakeGoogleCalendarApi()),
        FakeStates(),
        FakeCredentialStore(),
        FakeGoogleCalendarLinkRepository(),
    )
    with pytest.raises(AuthenticationError):
        await use_case.execute("code", "forged", None)
    with pytest.raises(GoogleScopeNotGrantedError):
        await use_case.execute("code", "state-1", "email")
    with pytest.raises(InvalidOperationError) as excinfo:
        await use_case.execute("bad", "state-1", None)
    assert not isinstance(excinfo.value, GoogleScopeNotGrantedError)


async def test_tokens_refresh_keeps_refresh_token() -> None:
    api, store = FakeGoogleCalendarApi(), FakeCredentialStore()
    await store.save(1, GOOGLE, _payload(timedelta(minutes=1)))

    tokens = await valid_google_tokens(_client(api), store, 1)

    assert api.token_grants == ["refresh_token"]
    assert tokens.access_token == "access-1" and tokens.refresh_token == "refresh-0"
    assert store.data[(1, GOOGLE)]["refresh_token"] == "refresh-0"

    fresh = await valid_google_tokens(_client(api), store, 1)
    assert fresh.access_token == "access-1" and api.token_grants == ["refresh_token"]

    with pytest.raises(NotFoundError):
        await valid_google_tokens(_client(api), store, 2)


async def test_list_and_select_calendar() -> None:
    api, store = FakeGoogleCalendarApi(), FakeCredentialStore()
    links, events = FakeGoogleCalendarLinkRepository(), FakeCalendarEventRepository()
    await store.save(1, GOOGLE, _payload(timedelta(hours=1)))
    select = SelectGoogleCalendar(_client(api), store, links, events)
    with pytest.raises(NotFoundError):
        await select.execute(1, "me@example.com")  # not linked yet

    await links.save(GoogleCalendarLink(user_id=1, sync_token="tok"))
    calendars = await ListGoogleCalendars(_client(api), store).execute(1)
    assert [c.writable for c in calendars] == [True, True, False]

    # Choosing the primary calendar while on "primary" changes nothing.
    link = await select.execute(1, "me@example.com")
    assert link.calendar_id == "primary" and link.sync_token == "tok"

    start = datetime(2026, 10, 12, 9, tzinfo=UTC)
    local = await events.add(
        CalendarEvent(
            1, "Mine", start, start + timedelta(hours=1), google_event_id="g1", sync_pending=False
        )
    )
    await events.add(
        CalendarEvent(
            1,
            "Theirs",
            start,
            start + timedelta(hours=1),
            source=EventSource.GOOGLE,
            google_event_id="g2",
        )
    )
    link = await select.execute(1, "family@group.calendar.google.com")
    assert link.calendar_id == "family@group.calendar.google.com" and link.sync_token is None
    assert local.id is not None
    [kept] = events.events.values()
    assert kept.id == local.id and kept.google_event_id is None and kept.sync_pending

    with pytest.raises(InvalidOperationError):
        await select.execute(1, "holidays@group.v.calendar.google.com")
    with pytest.raises(NotFoundError):
        await select.execute(1, "nope")


async def test_google_status_reports_connection_and_linked_calendar() -> None:
    store, links = FakeCredentialStore(), FakeGoogleCalendarLinkRepository()
    status = GetGoogleStatus(store, links)
    assert await status.execute(1) == GoogleConnectionStatus(connected=False)

    await store.save(1, GOOGLE, _payload(timedelta(hours=1)))
    assert await status.execute(1) == GoogleConnectionStatus(connected=True)

    synced = datetime(2026, 10, 10, 12, tzinfo=UTC)
    await links.save(GoogleCalendarLink(user_id=1, calendar_id="family", last_synced_at=synced))
    assert await status.execute(1) == GoogleConnectionStatus(
        connected=True, calendar_id="family", last_synced_at=synced
    )
    # Another user's credentials and link never leak into this user's status.
    assert await status.execute(2) == GoogleConnectionStatus(connected=False)
