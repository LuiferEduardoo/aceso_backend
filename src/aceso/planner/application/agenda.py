from dataclasses import dataclass, field
from datetime import UTC, date, timedelta

from aceso.planner.application.ranges import day_bounds, validate_range
from aceso.planner.domain.entities import CalendarEvent, Habit, Task
from aceso.planner.domain.ports import CalendarEventRepository, HabitRepository, TaskRepository


@dataclass(slots=True)
class HabitOccurrence:
    habit: Habit
    count: int
    completed: bool


@dataclass(slots=True)
class AgendaDay:
    day: date
    events: list[CalendarEvent] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    habits: list[HabitOccurrence] = field(default_factory=list)


def _habit_active_on(habit: Habit, day: date) -> bool:
    if habit.archived_at is not None and day > habit.archived_at.date():
        return False
    return habit.scheduled_on(day)


class Agenda:
    """One per-day view merging events, due/scheduled tasks and expected habits (UTC days)."""

    def __init__(
        self,
        events: CalendarEventRepository,
        tasks: TaskRepository,
        habits: HabitRepository,
    ) -> None:
        self._events = events
        self._tasks = tasks
        self._habits = habits

    async def between(self, user_id: int, start: date, end: date) -> list[AgendaDay]:
        validate_range(start, end)
        start_at, end_at = day_bounds(start, end)
        # Habit-linked events are recurring in Google; locally the habit occurrences show them.
        events = [
            e
            for e in await self._events.list_range(user_id, start_at, end_at)
            if e.habit_id is None
        ]
        tasks = await self._tasks.list_between(user_id, start, end, start_at, end_at)
        habits = await self._habits.list_all(user_id, include_archived=True)
        counts = {
            (log.habit_id, log.day): log.count
            for log in await self._habits.list_user_logs(user_id, start, end)
        }

        days: list[AgendaDay] = []
        day = start
        while day <= end:
            day_start, day_end = day_bounds(day, day)
            agenda_day = AgendaDay(day=day)
            agenda_day.events = [e for e in events if e.overlaps(day_start, day_end)]
            agenda_day.tasks = [
                t
                for t in tasks
                if t.due_date == day
                or (
                    t.scheduled_start is not None
                    and t.scheduled_start.astimezone(UTC).date() == day
                )
            ]
            for habit in habits:
                if _habit_active_on(habit, day):
                    count = counts.get((habit.id, day), 0)
                    agenda_day.habits.append(
                        HabitOccurrence(habit, count, count >= habit.target_count)
                    )
            days.append(agenda_day)
            day += timedelta(days=1)
        return days
