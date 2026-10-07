from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, status
from pydantic import AwareDatetime

from aceso.identity.api.deps import CurrentUserIdDep
from aceso.running.api.deps import (
    ActivityRepositoryDep,
    OAuthStateSignerDep,
    StravaGatewayDep,
)
from aceso.running.api.schemas import (
    ActivityRead,
    AuthorizationUrl,
    StravaConnected,
    SyncResult,
)
from aceso.running.application.activities import ActivityQueries
from aceso.running.application.strava import (
    CompleteStravaAuthorization,
    StartStravaAuthorization,
    SyncStravaActivities,
)
from aceso.shared.api.deps import CredentialStoreDep
from aceso.shared.domain.credentials import IntegrationProvider
from aceso.shared.domain.errors import InvalidOperationError

strava_router = APIRouter(prefix="/running/strava", tags=["running"])
activities_router = APIRouter(prefix="/running/activities", tags=["running"])


@strava_router.get("/authorize", summary="URL to send the user to for Strava consent")
async def strava_authorize(
    user_id: CurrentUserIdDep, gateway: StravaGatewayDep, states: OAuthStateSignerDep
) -> AuthorizationUrl:
    url = StartStravaAuthorization(gateway, states).execute(user_id)
    return AuthorizationUrl(authorization_url=url)


@strava_router.get(
    "/callback", summary="Strava redirect target; the signed `state` identifies the user"
)
async def strava_callback(
    gateway: StravaGatewayDep,
    states: OAuthStateSignerDep,
    credentials: CredentialStoreDep,
    state: Annotated[str, Query()],
    code: Annotated[str | None, Query()] = None,
    scope: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> StravaConnected:
    if error or not code:
        raise InvalidOperationError(f"Strava authorization failed: {error or 'missing code'}")
    await CompleteStravaAuthorization(gateway, states, credentials).execute(code, state, scope)
    return StravaConnected()


@strava_router.post("/sync")
async def strava_sync(
    user_id: CurrentUserIdDep,
    gateway: StravaGatewayDep,
    credentials: CredentialStoreDep,
    activities: ActivityRepositoryDep,
    after: Annotated[AwareDatetime | None, Query(description="Only activities after this")] = None,
) -> SyncResult:
    synced = await SyncStravaActivities(gateway, credentials, activities).execute(user_id, after)
    return SyncResult(synced=synced)


@strava_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def strava_disconnect(user_id: CurrentUserIdDep, credentials: CredentialStoreDep) -> None:
    await credentials.delete(user_id, IntegrationProvider.STRAVA)


@activities_router.get("")
async def list_activities(
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    user_id: CurrentUserIdDep,
    activities: ActivityRepositoryDep,
) -> list[ActivityRead]:
    items = await ActivityQueries(activities).between(user_id, start, end)
    return [ActivityRead.model_validate(a) for a in items]


@activities_router.get("/{activity_id}")
async def get_activity(
    activity_id: Annotated[int, Path(ge=1)],
    user_id: CurrentUserIdDep,
    activities: ActivityRepositoryDep,
) -> ActivityRead:
    return ActivityRead.model_validate(await ActivityQueries(activities).get(user_id, activity_id))
