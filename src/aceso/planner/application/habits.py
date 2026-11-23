from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aceso.planner.application.habit_stats import HabitStats, compute_stats
from aceso.planner.application.ranges import validate_range
from aceso.planner.domain.entities import Habit, HabitFrequency, HabitLog
from aceso.planner.domain.ports import HabitRepository
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

HABIT_FIELDS = {
    "name",
    "description",
    "frequency",
    "weekdays",
    "times_per_week",
    "target_count",
    "unit",
    "start_date",
    "time_of_day",
    "duration_min",
    "timezone",
    "sync_to_calendar",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _validate_habit(habit: Habit) -> None:
    if habit.frequency == HabitFrequency.WEEKDAYS:
        if not habit.weekdays or any(not 0 <= d <= 6 for d in habit.weekdays):
            raise InvalidOperationError("weekdays needs at least one day between 0 and 6")
        habit.weekdays = sorted(set(habit.weekdays))
    else:
        habit.weekdays = []
    if habit.frequency == HabitFrequency.TIMES_PER_WEEK:
        if habit.times_per_week is None or not 1 <= habit.times_per_week <= 7:
            raise InvalidOperationError("times_per_week must be between 1 and 7")
    else:
        habit.times_per_week = None
    if habit.target_count < 1:
        raise InvalidOperationError("target_count must be at least 1")
    try:
        ZoneInfo(habit.timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise InvalidOperationError(f"Unknown timezone '{habit.timezone}'") from exc
    if habit.sync_to_calendar and habit.time_of_day is None:
        raise InvalidOperationError("sync_to_calendar needs a time_of_day")


class HabitService:
    def __init__(self, habits: HabitRepository, clock: Callable[[], datetime] = _utcnow) -> None:
        self._habits = habits
        self._clock = clock

    async def create(self, habit: Habit) -> Habit:
        _validate_habit(habit)
        return await self._habits.add(habit)

    async def list_all(self, user_id: int, include_archived: bool = False) -> list[Habit]:
        return await self._habits.list_all(user_id, include_archived)

    async def get(self, user_id: int, habit_id: int) -> Habit:
        habit = await self._habits.get(user_id, habit_id)
        if habit is None:
            raise NotFoundError("Habit not found")
        return habit

    async def update(self, user_id: int, habit_id: int, changes: dict[str, Any]) -> Habit:
        habit = await self.get(user_id, habit_id)
        for name, value in changes.items():
            if name in HABIT_FIELDS:
                setattr(habit, name, value)
        _validate_habit(habit)
        return await self._habits.update(habit)

    async def archive(self, user_id: int, habit_id: int) -> Habit:
        habit = await self.get(user_id, habit_id)
        if habit.archived_at is None:
            habit.archived_at = self._clock()
            habit = await self._habits.update(habit)
        return habit

    async def unarchive(self, user_id: int, habit_id: int) -> Habit:
        habit = await self.get(user_id, habit_id)
        if habit.archived_at is not None:
            habit.archived_at = None
            habit = await self._habits.update(habit)
        return habit

    async def delete(self, user_id: int, habit_id: int) -> None:
        await self._habits.delete(await self.get(user_id, habit_id))


class HabitTracking:
    """Daily check-ins and statistics for a habit."""

    def __init__(self, habits: HabitRepository, clock: Callable[[], datetime] = _utcnow) -> None:
        self._habits = habits
        self._clock = clock

    async def log(
        self, user_id: int, habit_id: int, day: date, count: int = 1, note: str | None = None
    ) -> HabitLog:
        habit = await self._get(user_id, habit_id)
        if habit.archived:
            raise InvalidOperationError("Archived habits cannot be logged")
        if day < habit.start_date:
            raise InvalidOperationError("Cannot log a day before the habit start_date")
        if count < 1:
            raise InvalidOperationError("count must be at least 1")
        assert habit.id is not None
        return await self._habits.upsert_log(
            HabitLog(habit_id=habit.id, day=day, count=count, note=note)
        )

    async def unlog(self, user_id: int, habit_id: int, day: date) -> None:
        habit = await self._get(user_id, habit_id)
        assert habit.id is not None
        if not await self._habits.delete_log(habit.id, day):
            raise NotFoundError("Habit log not found")

    async def logs(self, user_id: int, habit_id: int, start: date, end: date) -> list[HabitLog]:
        validate_range(start, end)
        habit = await self._get(user_id, habit_id)
        assert habit.id is not None
        return await self._habits.list_logs(habit.id, start, end)

    async def stats(self, user_id: int, habit_id: int, start: date, end: date) -> HabitStats:
        validate_range(start, end)
        habit = await self._get(user_id, habit_id)
        assert habit.id is not None
        today = self._clock().date()
        logs = await self._habits.list_logs(habit.id, end=today)
        return compute_stats(habit, logs, start, end, today)

    async def _get(self, user_id: int, habit_id: int) -> Habit:
        habit = await self._habits.get(user_id, habit_id)
        if habit is None:
            raise NotFoundError("Habit not found")
        return habit
