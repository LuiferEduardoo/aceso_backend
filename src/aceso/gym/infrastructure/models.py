from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

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
