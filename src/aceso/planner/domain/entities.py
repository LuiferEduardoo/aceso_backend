from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum


class HabitFrequency(StrEnum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    TIMES_PER_WEEK = "times_per_week"


@dataclass(slots=True)
class Habit:
    """A recurring personal habit. `weekdays` uses 0=Monday .. 6=Sunday."""

    user_id: int
    name: str
    start_date: date
    frequency: HabitFrequency = HabitFrequency.DAILY
    weekdays: list[int] = field(default_factory=list)
    times_per_week: int | None = None
    target_count: int = 1
    unit: str | None = None
    description: str | None = None
    time_of_day: time | None = None
    duration_min: int | None = None
    timezone: str = "UTC"
    sync_to_calendar: bool = False
    archived_at: datetime | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def archived(self) -> bool:
        return self.archived_at is not None

    def scheduled_on(self, day: date) -> bool:
        """Whether the habit is expected on `day` (any day counts for times_per_week)."""
        if day < self.start_date:
            return False
        if self.frequency == HabitFrequency.WEEKDAYS:
            return day.weekday() in self.weekdays
        return True


@dataclass(slots=True)
class HabitLog:
    habit_id: int
    day: date
    count: int = 1
    note: str | None = None
    id: int | None = None

    def meets(self, habit: Habit) -> bool:
        return self.count >= habit.target_count


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(slots=True)
class Task:
    user_id: int
    title: str
    notes: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    completed_at: datetime | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_scheduled(self) -> bool:
        return self.scheduled_start is not None and self.scheduled_end is not None
