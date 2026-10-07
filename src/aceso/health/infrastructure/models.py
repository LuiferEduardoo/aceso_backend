from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from aceso.shared.infrastructure.db import Base, IdMixin, TimestampMixin

NON_NEGATIVE_SUMMARY_COLUMNS = (
    "steps",
    "distance_m",
    "calories_active",
    "calories_total",
    "active_minutes",
)
SOURCE_CHECK = "source IN ('garmin', 'mi_fitness', 'health_connect', 'manual')"


def _user_fk() -> Mapped[int]:
    return mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))


class DailySummaryModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "health_daily_summaries"

    user_id: Mapped[int] = _user_fk()
    source: Mapped[str] = mapped_column(Text)
    day: Mapped[date] = mapped_column(Date)
    steps: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Double)
    calories_active: Mapped[int | None] = mapped_column(Integer)
    calories_total: Mapped[int | None] = mapped_column(Integer)
    active_minutes: Mapped[int | None] = mapped_column(Integer)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    stress_avg: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), sort_order=11
    )

    __table_args__ = (
        UniqueConstraint("user_id", "day", "source"),
        CheckConstraint(SOURCE_CHECK, name="source"),
        CheckConstraint(
            " AND ".join(f"({c} IS NULL OR {c} >= 0)" for c in NON_NEGATIVE_SUMMARY_COLUMNS),
            name="non_negative",
        ),
    )


class HealthSampleModel(IdMixin, Base):
    __tablename__ = "health_samples"

    user_id: Mapped[int] = _user_fk()
    source: Mapped[str] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[float] = mapped_column(Double)

    __table_args__ = (
        UniqueConstraint("user_id", "metric", "recorded_at", "source"),
        CheckConstraint(SOURCE_CHECK, name="source"),
        CheckConstraint(
            "metric IN ('heart_rate', 'stress', 'spo2', 'respiration', 'body_battery')",
            name="metric",
        ),
        Index("ix_health_samples_recorded_at_brin", "recorded_at", postgresql_using="brin"),
    )


class SleepSessionModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "sleep_sessions"

    user_id: Mapped[int] = _user_fk()
    source: Mapped[str] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deep_s: Mapped[int | None] = mapped_column(Integer)
    light_s: Mapped[int | None] = mapped_column(Integer)
    rem_s: Mapped[int | None] = mapped_column(Integer)
    awake_s: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("user_id", "source", "start_at"),
        Index("ix_sleep_sessions_user_id_start_at", "user_id", "start_at"),
        CheckConstraint(SOURCE_CHECK, name="source"),
        CheckConstraint("end_at > start_at", name="end_after_start"),
        CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="score"),
    )
