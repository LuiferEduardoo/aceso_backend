from datetime import date, datetime, time
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from aceso.planner.application.habit_stats import StreakUnit
from aceso.planner.domain.entities import (
    DEFAULT_TIMEZONE,
    EventSource,
    HabitFrequency,
    TaskPriority,
    TaskStatus,
)

Weekday = Annotated[int, Field(ge=0, le=6, description="0=Monday .. 6=Sunday")]


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    frequency: HabitFrequency = HabitFrequency.DAILY
    weekdays: list[Weekday] = Field(default=[], description="Required for 'weekdays'")
    times_per_week: int | None = Field(
        default=None, ge=1, le=7, description="Required for 'times_per_week'"
    )
    target_count: int = Field(default=1, ge=1, description="Count needed to complete a day")
    unit: str | None = None
    start_date: date
    time_of_day: time | None = None
    duration_min: int | None = Field(default=None, gt=0)
    timezone: str = Field(default=DEFAULT_TIMEZONE, description="IANA zone used for time_of_day")
    sync_to_calendar: bool = False


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    frequency: HabitFrequency | None = None
    weekdays: list[Weekday] | None = None
    times_per_week: int | None = Field(default=None, ge=1, le=7)
    target_count: int | None = Field(default=None, ge=1)
    unit: str | None = None
    start_date: date | None = None
    time_of_day: time | None = None
    duration_min: int | None = Field(default=None, gt=0)
    timezone: str | None = None
    sync_to_calendar: bool | None = None


class HabitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    frequency: HabitFrequency
    weekdays: list[int]
    times_per_week: int | None
    target_count: int
    unit: str | None
    start_date: date
    time_of_day: time | None
    duration_min: int | None
    timezone: str
    sync_to_calendar: bool
    archived_at: datetime | None
    created_at: datetime


class HabitLogIn(BaseModel):
    count: int = Field(default=1, ge=1)
    note: str | None = None


class HabitLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    habit_id: int
    day: date
    count: int
    note: str | None


class HabitStatsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    streak_unit: StreakUnit
    current_streak: int
    best_streak: int
    completed: int
    expected: int
    completion_rate: float


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    scheduled_start: AwareDatetime | None = None
    scheduled_end: AwareDatetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    scheduled_start: AwareDatetime | None = None
    scheduled_end: AwareDatetime | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    notes: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    description: str | None = None
    location: str | None = None
    start_at: AwareDatetime
    end_at: AwareDatetime
    all_day: bool = Field(
        default=False,
        description="Spans whole calendar days in the planner timezone (America/Bogota)",
    )


class CalendarEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=1000)
    description: str | None = None
    location: str | None = None
    start_at: AwareDatetime | None = None
    end_at: AwareDatetime | None = None
    all_day: bool | None = None


class CalendarEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    location: str | None
    start_at: datetime
    end_at: datetime
    all_day: bool
    source: EventSource
    task_id: int | None
    habit_id: int | None
    google_event_id: str | None
    sync_pending: bool
    created_at: datetime
    updated_at: datetime


class AgendaHabitRead(BaseModel):
    habit_id: int
    name: str
    time_of_day: time | None
    duration_min: int | None
    target_count: int
    count: int
    completed: bool


class AgendaDayRead(BaseModel):
    date: date
    events: list[CalendarEventRead]
    tasks: list[TaskRead]
    habits: list[AgendaHabitRead]


class AuthorizationUrl(BaseModel):
    authorization_url: str


class GoogleConnected(BaseModel):
    status: str = "connected"


class GoogleCalendarRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    summary: str
    primary: bool
    access_role: str
    writable: bool


class GoogleCalendarSelect(BaseModel):
    calendar_id: str = Field(min_length=1)


class GoogleCalendarLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    calendar_id: str
    last_synced_at: datetime | None


class GoogleSyncResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pulled: int = Field(description="Remote changes applied locally")
    pushed: int = Field(description="Local events created or updated in Google")
    deleted: int = Field(description="Local deletions applied in Google")
