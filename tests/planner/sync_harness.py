"""Wires SyncGoogleCalendar to in-memory fakes and the fake Google API."""

from datetime import UTC, datetime, timedelta

from aceso.planner.application.google_sync import GoogleSyncResult, SyncGoogleCalendar
from aceso.planner.domain.entities import CalendarEvent, GoogleCalendarLink, OAuthTokens
from aceso.planner.infrastructure.google_calendar import GoogleCalendarClient
from aceso.shared.domain.credentials import IntegrationProvider
from tests.planner.fakes import (
    FakeCalendarEventRepository,
    FakeCredentialStore,
    FakeGoogleCalendarLinkRepository,
    FakeHabitRepository,
    FakeTaskRepository,
)
from tests.planner.google_mock import FakeGoogleCalendarApi

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)


class Harness:
    def __init__(self, api: FakeGoogleCalendarApi | None = None) -> None:
        self.api = api or FakeGoogleCalendarApi()
        self.credentials = FakeCredentialStore()
        self.links = FakeGoogleCalendarLinkRepository()
        self.events = FakeCalendarEventRepository()
        self.tasks = FakeTaskRepository()
        self.habits = FakeHabitRepository()
        self.last = GoogleSyncResult()

    async def connect(self) -> None:
        tokens = OAuthTokens("access-0", NOW + timedelta(hours=1), "refresh-0")
        await self.credentials.save(1, IntegrationProvider.GOOGLE, tokens.to_payload())
        await self.links.save(GoogleCalendarLink(user_id=1))

    async def sync(self) -> int:
        client = GoogleCalendarClient("cid", "secret", "http://cb", transport=self.api.transport())
        use_case = SyncGoogleCalendar(
            client,
            self.credentials,
            self.links,
            self.events,
            self.tasks,
            self.habits,
            clock=lambda: NOW,
        )
        self.last = await use_case.execute(1)
        return self.last.pulled

    def by_google_id(self, google_id: str) -> CalendarEvent:
        return next(e for e in self.events.events.values() if e.google_event_id == google_id)

    def sync_requests(self) -> list[dict[str, str]]:
        return [dict(r.url.params) for r in self.api.requests if r.url.path.endswith("/events")]
