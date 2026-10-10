from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aceso.gym.domain.entities import Equipment, ExerciseType, MuscleGroup
from aceso.shared.infrastructure.db import Base, IdMixin, TimestampMixin


def _sql_values(enum: type[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum)


class ExerciseModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "exercises"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    muscle_group: Mapped[str] = mapped_column(Text)
    secondary_muscles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    equipment: Mapped[str] = mapped_column(Text)
    exercise_type: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)
    photo_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(f"muscle_group IN ({_sql_values(MuscleGroup)})", name="muscle_group"),
        CheckConstraint(
            f"secondary_muscles <@ ARRAY[{_sql_values(MuscleGroup)}]::text[]",
            name="secondary_muscles",
        ),
        CheckConstraint(f"equipment IN ({_sql_values(Equipment)})", name="equipment"),
        CheckConstraint(f"exercise_type IN ({_sql_values(ExerciseType)})", name="exercise_type"),
        CheckConstraint("length(name) BETWEEN 1 AND 100", name="name_length"),
        Index("uq_exercises_user_id_name_lower", "user_id", func.lower(name), unique=True),
    )


class RoutineModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "routines"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["RoutineExerciseModel"]] = relationship(
        back_populates="routine",
        cascade="all, delete-orphan",
        order_by="RoutineExerciseModel.position",
        lazy="selectin",
    )

    __table_args__ = (CheckConstraint("length(name) BETWEEN 1 AND 100", name="name_length"),)


class RoutineExerciseModel(IdMixin, Base):
    __tablename__ = "routine_exercises"

    routine_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("routines.id", ondelete="CASCADE")
    )
    exercise_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("exercises.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    target_sets: Mapped[int | None] = mapped_column(Integer)
    target_reps: Mapped[int | None] = mapped_column(Integer)
    target_weight_kg: Mapped[float | None] = mapped_column(Double)
    target_duration_s: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    routine: Mapped[RoutineModel] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("routine_id", "position"),
        CheckConstraint("position >= 1", name="position_positive"),
        CheckConstraint("target_sets IS NULL OR target_sets BETWEEN 1 AND 100", name="sets"),
        CheckConstraint("target_reps IS NULL OR target_reps BETWEEN 1 AND 1000", name="reps"),
        CheckConstraint("target_weight_kg IS NULL OR target_weight_kg >= 0", name="weight"),
        CheckConstraint("target_duration_s IS NULL OR target_duration_s > 0", name="duration"),
    )


class WorkoutSessionModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "workout_sessions"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    scheduled_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default="planned")
    routine_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("routines.id", ondelete="SET NULL"), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["SessionExerciseModel"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SessionExerciseModel.position",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("status IN ('planned', 'completed', 'skipped')", name="status"),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="finished_after_started",
        ),
        Index("ix_workout_sessions_user_id_scheduled_date", "user_id", "scheduled_date"),
    )


class SessionExerciseModel(IdMixin, Base):
    __tablename__ = "session_exercises"

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workout_sessions.id", ondelete="CASCADE")
    )
    exercise_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("exercises.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    sets: Mapped[list["ExerciseSetModel"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ExerciseSetModel.set_number",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("session_id", "position"),
        CheckConstraint("position >= 1", name="position_positive"),
    )


class ExerciseSetModel(IdMixin, Base):
    __tablename__ = "exercise_sets"

    session_exercise_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("session_exercises.id", ondelete="CASCADE")
    )
    set_number: Mapped[int] = mapped_column(Integer)
    reps: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Double)
    added_weight_kg: Mapped[float | None] = mapped_column(Double)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Double)
    rpe: Mapped[float | None] = mapped_column(Double)
    completed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text)

    intervals: Mapped[list["SetIntervalModel"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SetIntervalModel.position",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("session_exercise_id", "set_number"),
        CheckConstraint("set_number >= 1", name="set_number_positive"),
        CheckConstraint(
            "num_nonnulls(reps, weight_kg, added_weight_kg, duration_s, distance_m) >= 1",
            name="has_metric",
        ),
        CheckConstraint("reps IS NULL OR reps >= 0", name="reps"),
        CheckConstraint("weight_kg IS NULL OR weight_kg >= 0", name="weight"),
        CheckConstraint("added_weight_kg IS NULL OR added_weight_kg >= 0", name="added_weight"),
        CheckConstraint("duration_s IS NULL OR duration_s > 0", name="duration"),
        CheckConstraint("distance_m IS NULL OR distance_m >= 0", name="distance"),
        CheckConstraint("rpe IS NULL OR rpe BETWEEN 1 AND 10", name="rpe"),
    )


class SetIntervalModel(IdMixin, Base):
    __tablename__ = "set_intervals"

    set_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("exercise_sets.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Double)
    speed: Mapped[float | None] = mapped_column(Double)
    incline_pct: Mapped[float | None] = mapped_column(Double)
    level: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("set_id", "position"),
        CheckConstraint("position >= 1", name="position_positive"),
        CheckConstraint("num_nonnulls(duration_s, distance_m) >= 1", name="has_length"),
        CheckConstraint("duration_s IS NULL OR duration_s > 0", name="duration"),
        CheckConstraint("distance_m IS NULL OR distance_m > 0", name="distance"),
        CheckConstraint("speed IS NULL OR speed >= 0", name="speed"),
        CheckConstraint("incline_pct IS NULL OR incline_pct BETWEEN -100 AND 100", name="incline"),
        CheckConstraint("level IS NULL OR level >= 0", name="level"),
    )
