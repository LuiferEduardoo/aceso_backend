"""Imports every SQLAlchemy model so Base.metadata is complete (Alembic, tests)."""

from aceso.identity.infrastructure import models as identity_models

__all__ = ["identity_models"]
