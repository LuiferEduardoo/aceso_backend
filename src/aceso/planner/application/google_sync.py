"""Two-way Google Calendar sync: pull remote changes, then push local ones."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aceso.planner.application.google import valid_google_tokens
from aceso.planner.application.habit_calendar import habit_rrule
from aceso.planner.domain.entities import (
    CalendarEvent,
    EventDraft,
    EventSource,
    GoogleCalendarLink,
    RemoteEvent,
)
from aceso.planner.domain.errors import RemoteEventMissingError, SyncTokenExpiredError
from aceso.planner.domain.ports import (
    CalendarEventRepository,
    GoogleCalendarGateway,
    GoogleCalendarLinkRepository,
    HabitRepository,
    TaskRepository,
)
from aceso.shared.domain.credentials import CredentialStore
from aceso.shared.domain.errors import NotFoundError

FULL_SYNC_PAST = timedelta(days=30)
FULL_SYNC_FUTURE = timedelta(days=365)
MAX_PAGES = 100
HABIT_REF_PREFIX = "habit:"


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class GoogleSyncResult:
    pulled: int = 0
    pushed: int = 0
    deleted: int = 0


def local_wins(local: CalendarEvent, remote: RemoteEvent) -> bool:
    """Last-write-wins: a pending local change beats the remote one only if it is newer."""
    if not local.sync_pending:
        return False
    local_time = local.deleted_at or local.updated_at
    if local_time is None:
        return False
    return remote.updated is None or local_time > remote.updated


class SyncGoogleCalendar:
    def __init__(
        self,
        gateway: GoogleCalendarGateway,
        credentials: CredentialStore,
        links: GoogleCalendarLinkRepository,
        events: CalendarEventRepository,
        tasks: TaskRepository,
        habits: HabitRepository,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._gateway = gateway
        self._credentials = credentials
        self._links = links
        self._events = events
        self._tasks = tasks
        self._habits = habits
        self._clock = clock

    async def execute(self, user_id: int) -> GoogleSyncResult:
        link = await self._links.get(user_id)
        if link is None:
            raise NotFoundError("Google account is not connected")
        tokens = await valid_google_tokens(self._gateway, self._credentials, user_id, self._clock)
        pulled = await self._pull(user_id, tokens.access_token, link)
        # Keep the pull's sync token even if the push fails half-way.
        await self._links.save(link)
        pushed, deleted = await self._push(user_id, tokens.access_token, link.calendar_id)
        link.last_synced_at = self._clock()
        await self._links.save(link)
        return GoogleSyncResult(pulled=pulled, pushed=pushed, deleted=deleted)

    # -- pull -------------------------------------------------------------------------------

    async def _pull(self, user_id: int, access_token: str, link: GoogleCalendarLink) -> int:
        full = link.sync_token is None
        try:
            remote, sync_token = await self._fetch(access_token, link, full)
        except SyncTokenExpiredError:
            full = True
            remote, sync_token = await self._fetch(access_token, link, full)

        habit_ids = await self._events.habit_google_ids(user_id)
        applied = 0
        for event in remote:
            if _mirrors_habit(event, habit_ids):
                continue  # Habit series are owned locally; Google is only a mirror.
            applied += await self._apply(user_id, event)
        if full:
            applied += await self._drop_missing(user_id, {e.id for e in remote})
        link.sync_token = sync_token
        return applied

    async def _fetch(
        self, access_token: str, link: GoogleCalendarLink, full: bool
    ) -> tuple[list[RemoteEvent], str | None]:
        now = self._clock()
        events: list[RemoteEvent] = []
        page_token: str | None = None
        for _ in range(MAX_PAGES):
            page = await self._gateway.list_events(
                access_token,
                link.calendar_id,
                sync_token=None if full else link.sync_token,
                time_min=now - FULL_SYNC_PAST if full else None,
                time_max=now + FULL_SYNC_FUTURE if full else None,
                page_token=page_token,
            )
            events.extend(page.events)
            page_token = page.next_page_token
            if not page_token:
                return events, page.next_sync_token
        return events, None  # Too many pages: next sync starts over with a full one.

    async def _apply(self, user_id: int, remote: RemoteEvent) -> int:
        local = await self._events.get_by_google_id(user_id, remote.id)
        if local is None and not remote.cancelled:
            local = await self._orphan_of(user_id, remote)
        if remote.cancelled:
            return await self._apply_cancel(local, remote)
        if remote.start_at is None or remote.end_at is None or remote.end_at <= remote.start_at:
            return 0
        if local is None:
            await self._events.add(
                _with_remote(
                    CalendarEvent(
                        user_id=user_id,
                        title=remote.title,
                        start_at=remote.start_at,
                        end_at=remote.end_at,
                        source=EventSource.GOOGLE,
                    ),
                    remote,
                )
            )
            return 1
        if local.etag is not None and local.etag == remote.etag:
            return 0  # Nothing new remotely (typically the echo of our own push).
        if local_wins(local, remote):
            return 0
        if local.deleted_at is not None:
            # Edited remotely after the local delete: bring it back as a standalone event.
            local.deleted_at, local.task_id, local.habit_id = None, None, None
        await self._events.update(_with_remote(local, remote))
        await self._mirror_on_task(local)
        return 1

    async def _orphan_of(self, user_id: int, remote: RemoteEvent) -> CalendarEvent | None:
        """A local event we pushed but never stored the Google id for (e.g. rolled back)."""
        kind, _, raw_id = (remote.aceso_ref or "").partition(":")
        if not raw_id.isdigit():
            return None
        if kind == "event":
            local = await self._events.get(user_id, int(raw_id))
        elif kind == "task":
            local = await self._events.get_by_task(user_id, int(raw_id))
        else:
            return None
        if local is None or local.google_event_id is not None:
            return None
        local.google_event_id = remote.id
        return await self._events.update(local)

    async def _apply_cancel(self, local: CalendarEvent | None, remote: RemoteEvent) -> int:
        if local is None:
            return 0
        if local.deleted_at is not None:
            await self._events.delete(local)  # Both sides agree: purge the tombstone.
            return 0
        if local_wins(local, remote):
            # Edited locally after the remote delete: push it again as a new event.
            local.google_event_id, local.etag, local.remote_updated_at = None, None, None
            await self._events.update(local)
            return 0
        await self._soft_delete(local)
        return 1

    async def _drop_missing(self, user_id: int, seen: set[str]) -> int:
        """After a full resync, synced events Google no longer has were deleted there."""
        now = self._clock()
        dropped = 0
        candidates = await self._events.list_synced_between(
            user_id, now - FULL_SYNC_PAST, now + FULL_SYNC_FUTURE
        )
        for local in candidates:
            if local.google_event_id not in seen:
                await self._soft_delete(local)
                dropped += 1
        return dropped

    async def _soft_delete(self, local: CalendarEvent) -> None:
        local.deleted_at = self._clock()
        local.sync_pending = False
        await self._events.update(local)
        if local.task_id is not None:
            task = await self._tasks.get(local.user_id, local.task_id)
            if task is not None and task.is_scheduled:
                task.scheduled_start = task.scheduled_end = None
                await self._tasks.update(task)

    async def _mirror_on_task(self, event: CalendarEvent) -> None:
        if event.task_id is None:
            return
        task = await self._tasks.get(event.user_id, event.task_id)
        if task is None:
            return
        task.title = event.title or task.title
        task.notes = event.description
        task.scheduled_start, task.scheduled_end = event.start_at, event.end_at
        await self._tasks.update(task)

    # -- push -------------------------------------------------------------------------------

    async def _push(self, user_id: int, access_token: str, calendar_id: str) -> tuple[int, int]:
        pushed = deleted = 0
        for event in await self._events.list_pending(user_id):
            if event.deleted_at is not None:
                if event.google_event_id is not None:
                    await self._gateway.delete_event(
                        access_token, calendar_id, event.google_event_id
                    )
                    deleted += 1
                await self._events.delete(event)
                continue
            draft = await self._draft(event)
            remote = None
            if event.google_event_id is not None:
                try:
                    remote = await self._gateway.patch_event(
                        access_token, calendar_id, event.google_event_id, draft
                    )
                except RemoteEventMissingError:
                    remote = None  # Deleted in Google meanwhile: create it again.
            if remote is None:
                remote = await self._gateway.insert_event(access_token, calendar_id, draft)
            event.google_event_id = remote.id
            event.etag = remote.etag
            event.remote_updated_at = remote.updated
            event.sync_pending = False
            await self._events.update(event)
            pushed += 1
        return pushed, deleted

    async def _draft(self, event: CalendarEvent) -> EventDraft:
        common = {
            "title": event.title,
            "description": event.description,
            "location": event.location,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "all_day": event.all_day,
        }
        if event.habit_id is not None:
            habit = await self._habits.get(event.user_id, event.habit_id)
            if habit is not None:
                return EventDraft(
                    **common,
                    aceso_ref=f"{HABIT_REF_PREFIX}{habit.id}",
                    timezone=habit.timezone,
                    recurrence=[habit_rrule(habit)],
                )
        if event.task_id is not None:
            return EventDraft(**common, aceso_ref=f"task:{event.task_id}")
        return EventDraft(**common, aceso_ref=f"event:{event.id}")


def _mirrors_habit(event: RemoteEvent, habit_ids: set[str]) -> bool:
    return (
        (event.aceso_ref or "").startswith(HABIT_REF_PREFIX)
        or event.id in habit_ids
        or event.recurring_event_id in habit_ids
    )


def _with_remote(event: CalendarEvent, remote: RemoteEvent) -> CalendarEvent:
    assert remote.start_at is not None and remote.end_at is not None
    event.title = remote.title
    event.description = remote.description
    event.location = remote.location
    event.start_at, event.end_at, event.all_day = remote.start_at, remote.end_at, remote.all_day
    event.google_event_id = remote.id
    event.etag = remote.etag
    event.remote_updated_at = remote.updated
    event.sync_pending = False
    return event
