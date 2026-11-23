from copy import deepcopy
from datetime import UTC, date, datetime
from typing import Any

from aceso.planner.domain.entities import (
    CalendarEvent,
    EventSource,
    GoogleCalendarLink,
    Habit,
    HabitLog,
    Task,
    TaskStatus,
)
from aceso.shared.domain.credentials import IntegrationProvider
from aceso.shared.domain.errors import AuthenticationError


class FakeHabitRepository:
    def __init__(self) -> None:
        self.habits: dict[int, Habit] = {}
        self.logs: dict[tuple[int, date], HabitLog] = {}
        self._id = 0
        self._log_id = 0

    async def add(self, habit: Habit) -> Habit:
        habit = deepcopy(habit)
        self._id += 1
        habit.id = self._id
        habit.created_at = habit.updated_at = datetime.now(UTC)
        self.habits[habit.id] = habit
        return deepcopy(habit)

    async def get(self, user_id: int, habit_id: int) -> Habit | None:
        habit = self.habits.get(habit_id)
        return deepcopy(habit) if habit and habit.user_id == user_id else None

    async def list_all(self, user_id: int, include_archived: bool) -> list[Habit]:
        return [
            deepcopy(h)
            for h in self.habits.values()
            if h.user_id == user_id and (include_archived or h.archived_at is None)
        ]

    async def update(self, habit: Habit) -> Habit:
        assert habit.id is not None
        habit = deepcopy(habit)
        habit.updated_at = datetime.now(UTC)
        self.habits[habit.id] = habit
        return deepcopy(habit)

    async def delete(self, habit: Habit) -> None:
        assert habit.id is not None
        self.habits.pop(habit.id, None)
        self.logs = {k: v for k, v in self.logs.items() if k[0] != habit.id}

    async def upsert_log(self, log: HabitLog) -> HabitLog:
        log = deepcopy(log)
        existing = self.logs.get((log.habit_id, log.day))
        if existing is None:
            self._log_id += 1
            log.id = self._log_id
        else:
            log.id = existing.id
        self.logs[(log.habit_id, log.day)] = log
        return deepcopy(log)

    async def delete_log(self, habit_id: int, day: date) -> bool:
        return self.logs.pop((habit_id, day), None) is not None

    async def list_logs(
        self, habit_id: int, start: date | None = None, end: date | None = None
    ) -> list[HabitLog]:
        return sorted(
            (
                deepcopy(log)
                for (hid, day), log in self.logs.items()
                if hid == habit_id
                and (start is None or day >= start)
                and (end is None or day <= end)
            ),
            key=lambda log: log.day,
        )

    async def list_user_logs(self, user_id: int, start: date, end: date) -> list[HabitLog]:
        owned = {h.id for h in self.habits.values() if h.user_id == user_id}
        return sorted(
            (
                deepcopy(log)
                for (hid, day), log in self.logs.items()
                if hid in owned and start <= day <= end
            ),
            key=lambda log: (log.day, log.habit_id),
        )


class FakeTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[int, Task] = {}
        self._id = 0

    async def add(self, task: Task) -> Task:
        task = deepcopy(task)
        self._id += 1
        task.id = self._id
        task.created_at = task.updated_at = datetime.now(UTC)
        self.tasks[task.id] = task
        return deepcopy(task)

    async def get(self, user_id: int, task_id: int) -> Task | None:
        task = self.tasks.get(task_id)
        return deepcopy(task) if task and task.user_id == user_id else None

    async def list_filtered(
        self,
        user_id: int,
        status: TaskStatus | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
    ) -> list[Task]:
        return [
            deepcopy(t)
            for t in self.tasks.values()
            if t.user_id == user_id
            and (status is None or t.status == status)
            and (due_from is None or (t.due_date is not None and t.due_date >= due_from))
            and (due_to is None or (t.due_date is not None and t.due_date <= due_to))
        ]

    async def list_between(
        self, user_id: int, start: date, end: date, start_at: datetime, end_at: datetime
    ) -> list[Task]:
        return [
            deepcopy(t)
            for t in self.tasks.values()
            if t.user_id == user_id
            and (
                (t.due_date is not None and start <= t.due_date <= end)
                or (
                    t.scheduled_start is not None
                    and t.scheduled_end is not None
                    and t.scheduled_start < end_at
                    and t.scheduled_end > start_at
                )
            )
        ]

    async def update(self, task: Task) -> Task:
        assert task.id is not None
        task = deepcopy(task)
        task.updated_at = datetime.now(UTC)
        self.tasks[task.id] = task
        return deepcopy(task)

    async def delete(self, task: Task) -> None:
        assert task.id is not None
        self.tasks.pop(task.id, None)


class FakeCalendarEventRepository:
    def __init__(self) -> None:
        self.events: dict[int, CalendarEvent] = {}
        self._id = 0

    def live(self, user_id: int) -> list[CalendarEvent]:
        return [e for e in self.events.values() if e.user_id == user_id and e.deleted_at is None]

    async def add(self, event: CalendarEvent) -> CalendarEvent:
        event = deepcopy(event)
        self._id += 1
        event.id = self._id
        event.created_at = event.updated_at = datetime.now(UTC)
        self.events[event.id] = event
        return deepcopy(event)

    async def get(self, user_id: int, event_id: int) -> CalendarEvent | None:
        event = self.events.get(event_id)
        if event is None or event.user_id != user_id or event.deleted_at is not None:
            return None
        return deepcopy(event)

    async def get_by_task(self, user_id: int, task_id: int) -> CalendarEvent | None:
        return next((deepcopy(e) for e in self.live(user_id) if e.task_id == task_id), None)

    async def list_range(self, user_id: int, start: datetime, end: datetime) -> list[CalendarEvent]:
        found = [deepcopy(e) for e in self.live(user_id) if e.overlaps(start, end)]
        return sorted(found, key=lambda e: e.start_at)

    async def update(self, event: CalendarEvent) -> CalendarEvent:
        assert event.id is not None
        event = deepcopy(event)
        event.updated_at = datetime.now(UTC)
        self.events[event.id] = event
        return deepcopy(event)

    async def delete(self, event: CalendarEvent) -> None:
        assert event.id is not None
        self.events.pop(event.id, None)

    async def get_by_habit(self, user_id: int, habit_id: int) -> CalendarEvent | None:
        return next((deepcopy(e) for e in self.live(user_id) if e.habit_id == habit_id), None)

    async def list_pending(self, user_id: int) -> list[CalendarEvent]:
        return [
            deepcopy(e)
            for e in self.events.values()
            if e.user_id == user_id
            and (e.sync_pending or (e.google_event_id is None and e.deleted_at is None))
        ]

    async def get_by_google_id(self, user_id: int, google_event_id: str) -> CalendarEvent | None:
        return next(
            (
                deepcopy(e)
                for e in self.events.values()
                if e.user_id == user_id and e.google_event_id == google_event_id
            ),
            None,
        )

    async def list_synced_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        return [
            deepcopy(e)
            for e in self.live(user_id)
            if e.google_event_id
            and e.habit_id is None
            and not e.sync_pending
            and start <= e.start_at < end
        ]

    async def habit_google_ids(self, user_id: int) -> set[str]:
        return {
            e.google_event_id
            for e in self.events.values()
            if e.user_id == user_id and e.habit_id is not None and e.google_event_id
        }

    async def reset_sync(self, user_id: int) -> None:
        for event_id, event in list(self.events.items()):
            if event.user_id != user_id:
                continue
            if event.source == EventSource.GOOGLE or event.deleted_at is not None:
                del self.events[event_id]
                continue
            event.google_event_id = event.etag = event.remote_updated_at = None
            event.sync_pending = True


class FakeGoogleCalendarLinkRepository:
    def __init__(self) -> None:
        self.links: dict[int, GoogleCalendarLink] = {}

    async def get(self, user_id: int) -> GoogleCalendarLink | None:
        link = self.links.get(user_id)
        return deepcopy(link) if link else None

    async def save(self, link: GoogleCalendarLink) -> GoogleCalendarLink:
        self.links[link.user_id] = deepcopy(link)
        return deepcopy(link)

    async def delete(self, user_id: int) -> None:
        self.links.pop(user_id, None)


class FakeCredentialStore:
    def __init__(self) -> None:
        self.data: dict[tuple[int, IntegrationProvider], dict[str, Any]] = {}

    async def get(self, user_id: int, provider: IntegrationProvider) -> dict[str, Any] | None:
        return self.data.get((user_id, provider))

    async def save(
        self, user_id: int, provider: IntegrationProvider, payload: dict[str, Any]
    ) -> None:
        self.data[(user_id, provider)] = payload

    async def delete(self, user_id: int, provider: IntegrationProvider) -> None:
        self.data.pop((user_id, provider), None)


class FakeStates:
    def issue(self, user_id: int) -> str:
        return f"state-{user_id}"

    def verify(self, state: str) -> int:
        if not state.startswith("state-"):
            raise AuthenticationError("Invalid state")
        return int(state.removeprefix("state-"))
