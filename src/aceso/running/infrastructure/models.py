from datetime import date, datetime
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aceso.shared.infrastructure.db import Base, IdMixin, TimestampMixin


class TrainingPlanModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_plans"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)

    runs: Mapped[list["PlannedRunModel"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: [PlannedRunModel.scheduled_date, PlannedRunModel.id],
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 100", name="name_length"),
        CheckConstraint("end_date >= start_date", name="end_after_start"),
    )


class PlannedRunModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "planned_runs"

    plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("training_plans.id", ondelete="CASCADE")
    )
    scheduled_date: Mapped[date] = mapped_column(Date)
    run_type: Mapped[str] = mapped_column(Text)
    target_distance_m: Mapped[float | None] = mapped_column(Double)
    target_duration_s: Mapped[int | None] = mapped_column(Integer)
    target_pace_s_per_km: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_planned_runs_plan_id_scheduled_date", "plan_id", "scheduled_date"),
        CheckConstraint(
            "run_type IN ('easy', 'tempo', 'interval', 'long', 'recovery', 'race')",
            name="run_type",
        ),
        CheckConstraint("target_distance_m IS NULL OR target_distance_m > 0", name="distance"),
        CheckConstraint("target_duration_s IS NULL OR target_duration_s > 0", name="duration"),
        CheckConstraint("target_pace_s_per_km IS NULL OR target_pace_s_per_km > 0", name="pace"),
    )


class ActivityModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "activities"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(Text)
    external_id: Mapped[str] = mapped_column(Text)
    sport_type: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    distance_m: Mapped[float | None] = mapped_column(Double)
    moving_time_s: Mapped[int | None] = mapped_column(Integer)
    elapsed_time_s: Mapped[int | None] = mapped_column(Integer)
    elevation_gain_m: Mapped[float | None] = mapped_column(Double)
    avg_hr: Mapped[float | None] = mapped_column(Double)
    max_hr: Mapped[float | None] = mapped_column(Double)
    avg_speed: Mapped[float | None] = mapped_column(Double)
    calories: Mapped[float | None] = mapped_column(Double)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), sort_order=11
    )

    __table_args__ = (
        UniqueConstraint("user_id", "source", "external_id"),
        Index("ix_activities_user_id_start_at", "user_id", "start_at"),
        CheckConstraint("source IN ('strava')", name="source"),
        CheckConstraint("distance_m IS NULL OR distance_m >= 0", name="distance"),
    )
