from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from aceso.planner.application.ranges import day_bounds, validate_range
from aceso.planner.domain.entities import CalendarEvent
from aceso.planner.domain.ports import CalendarEventRepository
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

EVENT_FIELDS = {"title", "description", "location", "start_at", "end_at", "all_day"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_event(event: CalendarEvent) -> CalendarEvent:
    if event.end_at <= event.start_at:
        raise InvalidOperationError("end_at must be after start_at")
    if event.all_day:
        # All-day events span whole UTC days: [first day 00:00, day after the last 00:00).
        start = datetime.combine(event.start_at.astimezone(UTC).date(), time.min, tzinfo=UTC)
        end = datetime.combine(event.end_at.astimezone(UTC).date(), time.min, tzinfo=UTC)
        event.start_at, event.end_at = start, max(end, start + timedelta(days=1))
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
        self, events: CalendarEventRepository, clock: Callable[[], datetime] = _utcnow
    ) -> None:
        self._events = events
        self._clock = clock

    async def create(self, event: CalendarEvent) -> CalendarEvent:
        event.sync_pending = True
        return await self._events.add(normalize_event(event))

    async def between(self, user_id: int, start: date, end: date) -> list[CalendarEvent]:
        validate_range(start, end)
        return await self._events.list_range(user_id, *day_bounds(start, end))

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
        return await self._events.update(normalize_event(event))

    async def delete(self, user_id: int, event_id: int) -> None:
        await discard_event(self._events, await self._editable(user_id, event_id), self._clock())

    async def _editable(self, user_id: int, event_id: int) -> CalendarEvent:
        event = await self.get(user_id, event_id)
        if event.is_linked:
            raise InvalidOperationError("This event belongs to a task or habit; edit that instead")
        return event
