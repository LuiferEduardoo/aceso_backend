"""Imports every SQLAlchemy model so Base.metadata is complete (Alembic, tests)."""

from aceso.gym.infrastructure import models as gym_models
from aceso.health.infrastructure import models as health_models
from aceso.identity.infrastructure import models as identity_models
from aceso.running.infrastructure import models as running_models
from aceso.shared.infrastructure import credentials as shared_credentials

__all__ = ["gym_models", "health_models", "identity_models", "running_models", "shared_credentials"]
