from datetime import date

from aceso.health.application.ingest import IngestHealthData
from aceso.health.domain.entities import HealthSource, IngestResult
from aceso.health.domain.ports import HealthProvider
from aceso.shared.domain.credentials import CredentialStore, IntegrationProvider
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

MAX_SYNC_DAYS = 31


class ConnectHealthProvider:
    def __init__(
        self,
        provider: HealthProvider,
        credentials: CredentialStore,
        integration: IntegrationProvider,
    ) -> None:
        self._provider = provider
        self._credentials = credentials
        self._integration = integration

    async def execute(self, user_id: int, email: str, password: str) -> None:
        payload = await self._provider.connect(email, password)
        await self._credentials.save(user_id, self._integration, payload)


class SyncHealthProvider:
    """Pull a date range from a provider and store it through the regular ingest path."""

    def __init__(
        self,
        provider: HealthProvider,
        credentials: CredentialStore,
        ingest: IngestHealthData,
        integration: IntegrationProvider,
        source: HealthSource,
    ) -> None:
        self._provider = provider
        self._credentials = credentials
        self._ingest = ingest
        self._integration = integration
        self._source = source

    async def execute(self, user_id: int, start: date, end: date) -> IngestResult:
        if end < start:
            raise InvalidOperationError("'to' must be on or after 'from'")
        if (end - start).days >= MAX_SYNC_DAYS:
            raise InvalidOperationError(f"Sync range cannot exceed {MAX_SYNC_DAYS} days")
        credentials = await self._credentials.get(user_id, self._integration)
        if credentials is None:
            raise NotFoundError(f"{self._integration.value.title()} account is not connected")
        batch, refreshed = await self._provider.fetch(credentials, start, end)
        if refreshed != credentials:
            await self._credentials.save(user_id, self._integration, refreshed)
        return await self._ingest.execute(user_id, self._source, batch)
