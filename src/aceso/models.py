"""Imports every SQLAlchemy model so Base.metadata is complete (Alembic, tests)."""

from aceso.gym.infrastructure import models as gym_models
from aceso.health.infrastructure import models as health_models
from aceso.identity.infrastructure import models as identity_models

__all__ = ["gym_models", "health_models", "identity_models"]
