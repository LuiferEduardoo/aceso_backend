from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import AwareDatetime

from aceso.health.api.deps import GarminProviderDep, HealthRepositoryDep
from aceso.health.api.schemas import (
    DailySummaryRead,
    GarminConnectRequest,
    HealthIngestRequest,
    HealthSampleRead,
    IngestResultRead,
    SleepSessionRead,
)
from aceso.health.application.ingest import IngestHealthData
from aceso.health.application.providers import ConnectHealthProvider, SyncHealthProvider
from aceso.health.application.queries import HealthQueries
from aceso.health.domain.entities import HealthSource, SampleMetric
from aceso.identity.api.deps import CurrentUserIdDep
from aceso.shared.api.deps import CredentialStoreDep
from aceso.shared.domain.credentials import IntegrationProvider

router = APIRouter(prefix="/health", tags=["health"])

FromDate = Annotated[date, Query(alias="from")]
ToDate = Annotated[date, Query(alias="to")]
SourceFilter = Annotated[HealthSource | None, Query()]


@router.post("/ingest", summary="Idempotent batch ingest from any source")
async def ingest(
    payload: HealthIngestRequest, user_id: CurrentUserIdDep, repository: HealthRepositoryDep
) -> IngestResultRead:
    result = await IngestHealthData(repository).execute(user_id, payload.source, payload.to_batch())
    return IngestResultRead.model_validate(result)


@router.get("/summaries")
async def list_daily_summaries(
    start: FromDate,
    end: ToDate,
    user_id: CurrentUserIdDep,
    repository: HealthRepositoryDep,
    source: SourceFilter = None,
) -> list[DailySummaryRead]:
    items = await HealthQueries(repository).daily_summaries(user_id, start, end, source)
    return [DailySummaryRead.model_validate(i) for i in items]


@router.get("/samples")
async def list_samples(
    metric: Annotated[SampleMetric, Query()],
    start: Annotated[AwareDatetime, Query(alias="from")],
    end: Annotated[AwareDatetime, Query(alias="to")],
    user_id: CurrentUserIdDep,
    repository: HealthRepositoryDep,
    source: SourceFilter = None,
) -> list[HealthSampleRead]:
    items = await HealthQueries(repository).samples(user_id, metric, start, end, source)
    return [HealthSampleRead.model_validate(i) for i in items]


@router.get("/sleep")
async def list_sleep_sessions(
    start: FromDate,
    end: ToDate,
    user_id: CurrentUserIdDep,
    repository: HealthRepositoryDep,
    source: SourceFilter = None,
) -> list[SleepSessionRead]:
    items = await HealthQueries(repository).sleep_sessions(user_id, start, end, source)
    return [SleepSessionRead.model_validate(i) for i in items]


@router.post("/garmin/connect", status_code=status.HTTP_204_NO_CONTENT)
async def connect_garmin(
    payload: GarminConnectRequest,
    user_id: CurrentUserIdDep,
    provider: GarminProviderDep,
    credentials: CredentialStoreDep,
) -> None:
    """Log in to Garmin Connect once and store the session tokens (encrypted)."""
    await ConnectHealthProvider(provider, credentials, IntegrationProvider.GARMIN).execute(
        user_id, payload.email, payload.password.get_secret_value()
    )


@router.delete("/garmin/connect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_garmin(user_id: CurrentUserIdDep, credentials: CredentialStoreDep) -> None:
    await credentials.delete(user_id, IntegrationProvider.GARMIN)


@router.post("/garmin/sync")
async def sync_garmin(
    start: FromDate,
    end: ToDate,
    user_id: CurrentUserIdDep,
    provider: GarminProviderDep,
    credentials: CredentialStoreDep,
    repository: HealthRepositoryDep,
) -> IngestResultRead:
    use_case = SyncHealthProvider(
        provider,
        credentials,
        IngestHealthData(repository),
        IntegrationProvider.GARMIN,
        HealthSource.GARMIN,
    )
    return IngestResultRead.model_validate(await use_case.execute(user_id, start, end))
