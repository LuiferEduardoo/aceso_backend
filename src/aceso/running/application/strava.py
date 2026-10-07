from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from aceso.running.domain.entities import OAuthTokens
from aceso.running.domain.ports import ActivityRepository, OAuthStateSigner, StravaGateway
from aceso.shared.domain.credentials import CredentialStore, IntegrationProvider
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError

REQUIRED_SCOPE = "activity:read"
REFRESH_MARGIN = timedelta(minutes=5)
PAGE_SIZE = 100
MAX_PAGES = 50


def _utcnow() -> datetime:
    return datetime.now(UTC)


class StartStravaAuthorization:
    def __init__(self, gateway: StravaGateway, states: OAuthStateSigner) -> None:
        self._gateway = gateway
        self._states = states

    def execute(self, user_id: int) -> str:
        return self._gateway.authorization_url(self._states.issue(user_id))


class CompleteStravaAuthorization:
    def __init__(
        self, gateway: StravaGateway, states: OAuthStateSigner, credentials: CredentialStore
    ) -> None:
        self._gateway = gateway
        self._states = states
        self._credentials = credentials

    async def execute(self, code: str, state: str, scope: str | None) -> int:
        user_id = self._states.verify(state)
        if scope is not None and not any(s.startswith(REQUIRED_SCOPE) for s in scope.split(",")):
            raise InvalidOperationError("Strava access to activities was not granted")
        tokens = await self._gateway.exchange_code(code)
        await self._credentials.save(user_id, IntegrationProvider.STRAVA, tokens.to_payload())
        return user_id


class SyncStravaActivities:
    """Import Strava activities (paginated) and upsert them; refreshes the token if needed."""

    def __init__(
        self,
        gateway: StravaGateway,
        credentials: CredentialStore,
        activities: ActivityRepository,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._gateway = gateway
        self._credentials = credentials
        self._activities = activities
        self._clock = clock

    async def execute(self, user_id: int, after: datetime | None = None) -> int:
        tokens = await self._valid_tokens(user_id)
        synced = 0
        for page in range(1, MAX_PAGES + 1):
            batch = await self._gateway.list_activities(
                tokens.access_token, after=after, page=page, per_page=PAGE_SIZE
            )
            for activity in batch:
                activity.user_id = user_id
            if batch:
                synced += await self._activities.upsert_many(batch)
            if len(batch) < PAGE_SIZE:
                break
        return synced

    async def _valid_tokens(self, user_id: int) -> OAuthTokens:
        payload = await self._credentials.get(user_id, IntegrationProvider.STRAVA)
        if payload is None:
            raise NotFoundError("Strava account is not connected")
        tokens = OAuthTokens.from_payload(payload)
        if tokens.expires_within(self._clock(), REFRESH_MARGIN):
            refreshed = await self._gateway.refresh(tokens.refresh_token)
            tokens = OAuthTokens(
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
                expires_at=refreshed.expires_at,
                athlete_id=refreshed.athlete_id or tokens.athlete_id,
            )
            await self._credentials.save(user_id, IntegrationProvider.STRAVA, tokens.to_payload())
        return tokens
