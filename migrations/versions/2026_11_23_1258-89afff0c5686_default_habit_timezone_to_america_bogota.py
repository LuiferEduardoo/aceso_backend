"""default habit timezone to america bogota

Revision ID: 89afff0c5686
Revises: 90a1ea9ff679
Create Date: 2026-11-23 12:58:55.927220

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "89afff0c5686"
down_revision: str | Sequence[str] | None = "90a1ea9ff679"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Only the default changes; existing habits keep their timezone."""
    op.alter_column("habits", "timezone", server_default="America/Bogota")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("habits", "timezone", server_default="UTC")
