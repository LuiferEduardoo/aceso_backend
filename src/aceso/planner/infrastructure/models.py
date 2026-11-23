from datetime import date, datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from aceso.planner.domain.entities import (
    EventSource,
    HabitFrequency,
    TaskPriority,
    TaskStatus,
)
from aceso.shared.infrastructure.db import Base, IdMixin, TimestampMixin


def _sql_values(enum: type) -> str:
    return ", ".join(f"'{member.value}'" for member in enum)


class HabitModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "habits"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[str] = mapped_column(Text)
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), server_default="{}")
    times_per_week: Mapped[int | None] = mapped_column(SmallInteger)
    target_count: Mapped[int] = mapped_column(Integer, server_default="1")
    unit: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    time_of_day: Mapped[time | None] = mapped_column(Time)
    duration_min: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(Text, server_default="UTC")
    sync_to_calendar: Mapped[bool] = mapped_column(Boolean, server_default="false")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), sort_order=11
    )

    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 100", name="name_length"),
        CheckConstraint(f"frequency IN ({_sql_values(HabitFrequency)})", name="frequency"),
        CheckConstraint(
            "weekdays <@ ARRAY[0, 1, 2, 3, 4, 5, 6]::smallint[]", name="weekdays_range"
        ),
        CheckConstraint(
            "frequency <> 'weekdays' OR cardinality(weekdays) > 0", name="weekdays_required"
        ),
        CheckConstraint(
            "(frequency = 'times_per_week') = (times_per_week IS NOT NULL)",
            name="times_per_week_required",
        ),
        CheckConstraint(
            "times_per_week IS NULL OR times_per_week BETWEEN 1 AND 7", name="times_per_week"
        ),
        CheckConstraint("target_count >= 1", name="target_count"),
        CheckConstraint("duration_min IS NULL OR duration_min > 0", name="duration_min"),
        CheckConstraint("NOT sync_to_calendar OR time_of_day IS NOT NULL", name="sync_needs_time"),
    )


class HabitLogModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "habit_logs"

    habit_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("habits.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    count: Mapped[int] = mapped_column(Integer, server_default="1")
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # The (habit_id, day) unique index also serves the habit_id foreign key.
        UniqueConstraint("habit_id", "day"),
        CheckConstraint("count >= 1", name="count"),
    )


class TaskModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "tasks"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="todo")
    priority: Mapped[str] = mapped_column(Text, server_default="medium")
    due_date: Mapped[date | None] = mapped_column(Date)
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), sort_order=11
    )

    __table_args__ = (
        # (user_id, due_date) also serves the user_id foreign key.
        Index("ix_tasks_user_id_due_date", "user_id", "due_date"),
        Index("ix_tasks_user_id_scheduled_start", "user_id", "scheduled_start"),
        CheckConstraint("length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint(f"status IN ({_sql_values(TaskStatus)})", name="status"),
        CheckConstraint(f"priority IN ({_sql_values(TaskPriority)})", name="priority"),
        CheckConstraint(
            "(scheduled_start IS NULL) = (scheduled_end IS NULL)", name="schedule_pair"
        ),
        CheckConstraint(
            "scheduled_end IS NULL OR scheduled_end > scheduled_start", name="schedule_order"
        ),
        CheckConstraint("(status = 'done') = (completed_at IS NOT NULL)", name="completed_at"),
    )


class CalendarEventModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "calendar_events"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, server_default="false")
    source: Mapped[str] = mapped_column(Text, server_default="local")
    # Tombstones outlive their task/habit, hence SET NULL.
    task_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    habit_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("habits.id", ondelete="SET NULL"), index=True
    )
    google_event_id: Mapped[str | None] = mapped_column(Text)
    etag: Mapped[str | None] = mapped_column(Text)
    remote_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_pending: Mapped[bool] = mapped_column(Boolean, server_default="true")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), sort_order=11
    )

    __table_args__ = (
        # (user_id, start_at) also serves the user_id foreign key.
        Index("ix_calendar_events_user_id_start_at", "user_id", "start_at"),
        Index(
            "uq_calendar_events_user_id_google_event_id",
            "user_id",
            "google_event_id",
            unique=True,
            postgresql_where=text("google_event_id IS NOT NULL"),
        ),
        Index(
            "uq_calendar_events_live_task_id",
            "task_id",
            unique=True,
            postgresql_where=text("task_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "uq_calendar_events_live_habit_id",
            "habit_id",
            unique=True,
            postgresql_where=text("habit_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        CheckConstraint("length(title) <= 1000", name="title_length"),
        CheckConstraint(f"source IN ({_sql_values(EventSource)})", name="source"),
        CheckConstraint("end_at > start_at", name="end_after_start"),
    )


class GoogleCalendarLinkModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "google_calendar_links"

    # The unique constraint's index also serves the foreign key.
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    calendar_id: Mapped[str] = mapped_column(Text, server_default="primary")
    sync_token: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), sort_order=11
    )

    __table_args__ = (CheckConstraint("length(calendar_id) >= 1", name="calendar_id"),)
