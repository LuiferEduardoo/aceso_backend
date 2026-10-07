from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from aceso.health.api.deps import HealthRepositoryDep
from aceso.health.api.schemas import (
    DailySummaryRead,
    HealthIngestRequest,
    HealthSampleRead,
    IngestResultRead,
    SleepSessionRead,
)
from aceso.health.application.ingest import IngestHealthData
from aceso.health.application.queries import HealthQueries
from aceso.health.domain.entities import HealthSource, SampleMetric
from aceso.identity.api.deps import CurrentUserIdDep

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
