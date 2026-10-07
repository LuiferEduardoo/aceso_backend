from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Double,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aceso.shared.infrastructure.db import Base, IdMixin, TimestampMixin


class ExerciseModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "exercises"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, server_default="strength")
    notes: Mapped[str | None] = mapped_column(Text)
    photo_key: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "category IN ('strength', 'cardio', 'bodyweight', 'other')", name="category"
        ),
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
