from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aceso.running.application.strava import (
    CompleteStravaAuthorization,
    SyncStravaActivities,
)
from aceso.running.domain.entities import Activity, OAuthTokens
from aceso.running.infrastructure.strava import StravaClient
from aceso.shared.domain.credentials import IntegrationProvider
from aceso.shared.domain.errors import (
    AuthenticationError,
    IntegrationError,
    InvalidOperationError,
    NotFoundError,
)
from tests.running.strava_mock import FakeStravaApi, strava_activity


class FakeCredentialStore:
    def __init__(self) -> None:
        self.data: dict[tuple[int, IntegrationProvider], dict[str, Any]] = {}

    async def get(self, user_id: int, provider: IntegrationProvider) -> dict[str, Any] | None:
        return self.data.get((user_id, provider))

    async def save(
        self, user_id: int, provider: IntegrationProvider, payload: dict[str, Any]
    ) -> None:
        self.data[(user_id, provider)] = payload

    async def delete(self, user_id: int, provider: IntegrationProvider) -> None:
        self.data.pop((user_id, provider), None)


class FakeActivityRepository:
    def __init__(self) -> None:
        self.items: dict[tuple, Activity] = {}

    async def upsert_many(self, activities: list[Activity]) -> int:
        for a in activities:
            self.items[(a.user_id, a.source, a.external_id)] = a
        return len(activities)

    async def get(self, user_id: int, activity_id: int) -> Activity | None:
        return None

    async def list_range(self, user_id: int, start: datetime, end: datetime) -> list[Activity]:
        return []


class FakeStates:
    def issue(self, user_id: int) -> str:
        return f"state-{user_id}"

    def verify(self, state: str) -> int:
        if not state.startswith("state-"):
            raise AuthenticationError("Invalid state")
        return int(state.removeprefix("state-"))


def _client(api: FakeStravaApi) -> StravaClient:
    return StravaClient("cid", "secret", "http://localhost/cb", transport=api.transport())


def _tokens(expires_in: timedelta) -> dict[str, Any]:
    return OAuthTokens(
        access_token="access-0",
        refresh_token="refresh-0",
        expires_at=datetime.now(UTC) + expires_in,
        athlete_id=99,
    ).to_payload()


def test_authorization_url_contains_state_and_scope() -> None:
    url = _client(FakeStravaApi()).authorization_url("abc")
    assert url.startswith("https://www.strava.com/oauth/authorize?")
    assert "state=abc" in url and "activity%3Aread_all" in url and "client_id=cid" in url


def test_unconfigured_client_fails_clearly() -> None:
    with pytest.raises(IntegrationError):
        StravaClient("", "", "http://localhost/cb").authorization_url("abc")


async def test_complete_authorization_stores_tokens() -> None:
    api, store = FakeStravaApi(), FakeCredentialStore()
    use_case = CompleteStravaAuthorization(_client(api), FakeStates(), store)

    user_id = await use_case.execute("code-1", "state-7", "read,activity:read_all")

    assert user_id == 7
    assert store.data[(7, IntegrationProvider.STRAVA)]["refresh_token"] == "refresh-1"
    assert api.token_grants == ["authorization_code"]


async def test_complete_authorization_rejects_bad_state_scope_and_code() -> None:
    use_case = CompleteStravaAuthorization(
        _client(FakeStravaApi()), FakeStates(), FakeCredentialStore()
    )
    with pytest.raises(AuthenticationError):
        await use_case.execute("code", "forged", None)
    with pytest.raises(InvalidOperationError):
        await use_case.execute("code", "state-1", "read")
    with pytest.raises(InvalidOperationError):
        await use_case.execute("bad", "state-1", None)


async def test_sync_paginates_and_upserts() -> None:
    api = FakeStravaApi([strava_activity(i) for i in range(1, 106)])
    store, repo = FakeCredentialStore(), FakeActivityRepository()
    await store.save(1, IntegrationProvider.STRAVA, _tokens(timedelta(hours=1)))

    synced = await SyncStravaActivities(_client(api), store, repo).execute(1)

    assert synced == 105
    assert len(repo.items) == 105
    pages = [r.url.params["page"] for r in api.requests if "activities" in r.url.path]
    assert pages == ["1", "2"]
    assert api.token_grants == []  # token still valid, no refresh
    activity = repo.items[(1, "strava", "1")]
    assert activity.distance_m == 10000.0 and activity.start_at.tzinfo is not None


async def test_sync_refreshes_expired_token_and_passes_after() -> None:
    api = FakeStravaApi()
    store = FakeCredentialStore()
    await store.save(1, IntegrationProvider.STRAVA, _tokens(timedelta(minutes=-1)))
    after = datetime(2026, 10, 1, tzinfo=UTC)

    await SyncStravaActivities(_client(api), store, FakeActivityRepository()).execute(1, after)

    assert api.token_grants == ["refresh_token"]
    saved = store.data[(1, IntegrationProvider.STRAVA)]
    assert saved["access_token"] == "access-1" and saved["athlete_id"] == 99
    request = next(r for r in api.requests if "activities" in r.url.path)
    assert request.headers["Authorization"] == "Bearer access-1"
    assert request.url.params["after"] == str(int(after.timestamp()))


async def test_sync_requires_connection() -> None:
    with pytest.raises(NotFoundError):
        await SyncStravaActivities(
            _client(FakeStravaApi()), FakeCredentialStore(), FakeActivityRepository()
        ).execute(1)


async def test_client_maps_http_errors() -> None:
    client = _client(FakeStravaApi())
    with pytest.raises(InvalidOperationError):
        await client.list_activities("revoked", after=None, page=1, per_page=10)
