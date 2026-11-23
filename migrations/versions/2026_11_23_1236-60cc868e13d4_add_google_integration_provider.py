"""add google integration provider

Revision ID: 60cc868e13d4
Revises: 3f988a203025
Create Date: 2026-11-23 12:36:37.243135

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "60cc868e13d4"
down_revision: str | Sequence[str] | None = "3f988a203025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_provider_check(providers: str) -> None:
    op.drop_constraint(
        op.f("ck_integration_credentials_provider"), "integration_credentials", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_integration_credentials_provider"),
        "integration_credentials",
        f"provider IN ({providers})",
    )


def upgrade() -> None:
    """Upgrade schema."""
    _replace_provider_check("'garmin', 'strava', 'google'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM integration_credentials WHERE provider = 'google'")
    _replace_provider_check("'garmin', 'strava'")
