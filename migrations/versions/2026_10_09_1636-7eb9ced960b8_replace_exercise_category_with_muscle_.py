"""replace exercise category with muscle and equipment fields

Revision ID: 7eb9ced960b8
Revises: bcfabe65d164
Create Date: 2026-10-09 16:36:47.571611

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7eb9ced960b8"
down_revision: str | Sequence[str] | None = "bcfabe65d164"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MUSCLE_GROUPS = (
    "'chest', 'back', 'shoulders', 'biceps', 'triceps', 'forearms', 'abs', "
    "'quadriceps', 'hamstrings', 'glutes', 'calves', 'full_body', 'cardio'"
)
EQUIPMENT = (
    "'barbell', 'dumbbell', 'machine', 'cable', 'kettlebell', 'bodyweight', "
    "'band', 'cardio_machine', 'other'"
)
EXERCISE_TYPES = "'compound', 'isolation', 'cardio'"


def upgrade() -> None:
    """Upgrade schema."""
    # Temporary server defaults backfill existing rows; category refines them below.
    op.add_column(
        "exercises",
        sa.Column("muscle_group", sa.Text(), server_default="full_body", nullable=False),
    )
    op.add_column(
        "exercises",
        sa.Column(
            "secondary_muscles",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "exercises", sa.Column("equipment", sa.Text(), server_default="other", nullable=False)
    )
    op.add_column(
        "exercises",
        sa.Column("exercise_type", sa.Text(), server_default="compound", nullable=False),
    )
    op.execute(
        "UPDATE exercises SET muscle_group = 'cardio', equipment = 'cardio_machine', "
        "exercise_type = 'cardio' WHERE category = 'cardio'"
    )
    op.execute("UPDATE exercises SET equipment = 'bodyweight' WHERE category = 'bodyweight'")
    for column in ("muscle_group", "equipment", "exercise_type"):
        op.alter_column("exercises", column, server_default=None)

    op.alter_column("exercises", "notes", new_column_name="instructions")
    op.drop_constraint(op.f("ck_exercises_category"), "exercises", type_="check")
    op.drop_column("exercises", "category")

    op.create_check_constraint(
        op.f("ck_exercises_muscle_group"), "exercises", f"muscle_group IN ({MUSCLE_GROUPS})"
    )
    op.create_check_constraint(
        op.f("ck_exercises_secondary_muscles"),
        "exercises",
        f"secondary_muscles <@ ARRAY[{MUSCLE_GROUPS}]::text[]",
    )
    op.create_check_constraint(
        op.f("ck_exercises_equipment"), "exercises", f"equipment IN ({EQUIPMENT})"
    )
    op.create_check_constraint(
        op.f("ck_exercises_exercise_type"), "exercises", f"exercise_type IN ({EXERCISE_TYPES})"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "exercises",
        sa.Column("category", sa.Text(), server_default="strength", nullable=False),
    )
    op.execute("UPDATE exercises SET category = 'cardio' WHERE exercise_type = 'cardio'")
    op.execute(
        "UPDATE exercises SET category = 'bodyweight' "
        "WHERE equipment = 'bodyweight' AND exercise_type <> 'cardio'"
    )
    op.create_check_constraint(
        op.f("ck_exercises_category"),
        "exercises",
        "category IN ('strength', 'cardio', 'bodyweight', 'other')",
    )
    op.alter_column("exercises", "instructions", new_column_name="notes")

    for name in ("exercise_type", "equipment", "secondary_muscles", "muscle_group"):
        op.drop_constraint(op.f(f"ck_exercises_{name}"), "exercises", type_="check")
        op.drop_column("exercises", name)
