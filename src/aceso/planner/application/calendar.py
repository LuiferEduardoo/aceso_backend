from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from aceso.planner.application.ranges import (
    DEFAULT_TZ,
    day_bounds,
    day_start,
    local_day,
    validate_range,
)
from aceso.planner.domain.entities import CalendarEvent
from aceso.planner.domain.ports import CalendarEventRepository
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

EVENT_FIELDS = {"title", "description", "location", "start_at", "end_at", "all_day"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_event(event: CalendarEvent, tz: ZoneInfo = DEFAULT_TZ) -> CalendarEvent:
    if event.end_at <= event.start_at:
        raise InvalidOperationError("end_at must be after start_at")
    if event.all_day:
        # All-day events span whole days in `tz`: [first day 00:00, day after the last 00:00).
        first = local_day(event.start_at, tz)
        last = max(local_day(event.end_at, tz), first + timedelta(days=1))
        event.start_at, event.end_at = day_start(first, tz), day_start(last, tz)
    return event


async def discard_event(
    events: CalendarEventRepository, event: CalendarEvent, now: datetime
) -> None:
    """Delete an event; one already in Google becomes a tombstone until the next push."""
    if event.google_event_id is None:
        await events.delete(event)
        return
    event.deleted_at = now
    event.sync_pending = True
    await events.update(event)


class CalendarService:
    def __init__(
        self,
        events: CalendarEventRepository,
        clock: Callable[[], datetime] = _utcnow,
        tz: ZoneInfo = DEFAULT_TZ,
    ) -> None:
        self._events = events
        self._clock = clock
        self._tz = tz

    async def create(self, event: CalendarEvent) -> CalendarEvent:
        event.sync_pending = True
        return await self._events.add(normalize_event(event, self._tz))

    async def between(self, user_id: int, start: date, end: date) -> list[CalendarEvent]:
        validate_range(start, end)
        return await self._events.list_range(user_id, *day_bounds(start, end, self._tz))

    async def get(self, user_id: int, event_id: int) -> CalendarEvent:
        event = await self._events.get(user_id, event_id)
        if event is None:
            raise NotFoundError("Event not found")
        return event

    async def update(self, user_id: int, event_id: int, changes: dict[str, Any]) -> CalendarEvent:
        event = await self._editable(user_id, event_id)
        for name, value in changes.items():
            if name in EVENT_FIELDS:
                setattr(event, name, value)
        event.sync_pending = True
        return await self._events.update(normalize_event(event, self._tz))

    async def delete(self, user_id: int, event_id: int) -> None:
        await discard_event(self._events, await self._editable(user_id, event_id), self._clock())

    async def _editable(self, user_id: int, event_id: int) -> CalendarEvent:
        event = await self.get(user_id, event_id)
        if event.is_linked:
            raise InvalidOperationError("This event belongs to a task or habit; edit that instead")
        return event
