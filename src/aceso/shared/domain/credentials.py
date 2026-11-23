from enum import StrEnum
from typing import Any, Protocol


class IntegrationProvider(StrEnum):
    GARMIN = "garmin"
    STRAVA = "strava"
    GOOGLE = "google"


class CredentialStore(Protocol):
    """Third-party credentials (OAuth tokens, sessions) per user, encrypted at rest."""

    async def get(self, user_id: int, provider: IntegrationProvider) -> dict[str, Any] | None: ...

    async def save(
        self, user_id: int, provider: IntegrationProvider, payload: dict[str, Any]
    ) -> None: ...

    async def delete(self, user_id: int, provider: IntegrationProvider) -> None: ...
