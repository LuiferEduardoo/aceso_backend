from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import Any

# IANA zone that defines planner "calendar days" unless configured otherwise.
DEFAULT_TIMEZONE = "America/Bogota"


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
    timezone: str = DEFAULT_TIMEZONE
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


class EventSource(StrEnum):
    LOCAL = "local"
    GOOGLE = "google"


@dataclass(slots=True)
class CalendarEvent:
    """A calendar entry. `deleted_at` marks a tombstone kept until Google learns of it."""

    user_id: int
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    description: str | None = None
    location: str | None = None
    source: EventSource = EventSource.LOCAL
    task_id: int | None = None
    habit_id: int | None = None
    google_event_id: str | None = None
    etag: str | None = None
    remote_updated_at: datetime | None = None
    sync_pending: bool = True
    deleted_at: datetime | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_linked(self) -> bool:
        return self.task_id is not None or self.habit_id is not None

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return self.start_at < end and self.end_at > start


@dataclass(slots=True, frozen=True)
class OAuthTokens:
    """Google OAuth tokens. A refresh response may omit `refresh_token` (None)."""

    access_token: str
    expires_at: datetime
    refresh_token: str | None = None

    def expires_within(self, now: datetime, margin: timedelta) -> bool:
        return self.expires_at <= now + margin

    def to_payload(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "OAuthTokens":
        return cls(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=datetime.fromisoformat(payload["expires_at"]),
        )


@dataclass(slots=True, frozen=True)
class GoogleCalendar:
    id: str
    summary: str
    primary: bool = False
    access_role: str = "reader"

    @property
    def writable(self) -> bool:
        return self.access_role in ("owner", "writer")


@dataclass(slots=True)
class GoogleCalendarLink:
    """Which Google calendar a user syncs with and where the incremental sync left off."""

    user_id: int
    calendar_id: str = "primary"
    sync_token: str | None = None
    last_synced_at: datetime | None = None
    id: int | None = None


ACESO_REF_KEY = "aceso_ref"


@dataclass(slots=True, frozen=True)
class RemoteEvent:
    """An event as Google reports it. Cancelled events may carry only `id` and `status`."""

    id: str
    status: str = "confirmed"
    updated: datetime | None = None
    etag: str | None = None
    title: str = ""
    description: str | None = None
    location: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool = False
    aceso_ref: str | None = None
    recurring_event_id: str | None = None

    @property
    def cancelled(self) -> bool:
        return self.status == "cancelled"


@dataclass(slots=True, frozen=True)
class RemoteEventPage:
    events: list[RemoteEvent]
    next_page_token: str | None = None
    next_sync_token: str | None = None


@dataclass(slots=True, frozen=True)
class EventDraft:
    """What we send to Google for one local event (a habit adds a recurrence rule)."""

    title: str
    start_at: datetime
    end_at: datetime
    aceso_ref: str
    all_day: bool = False
    description: str | None = None
    location: str | None = None
    timezone: str = DEFAULT_TIMEZONE
    recurrence: list[str] = field(default_factory=list)
