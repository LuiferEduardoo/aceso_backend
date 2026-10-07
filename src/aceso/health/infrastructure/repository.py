from collections.abc import Iterator, Sequence
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.health.domain.entities import (
    DailySummary,
    HealthSample,
    HealthSource,
    SampleMetric,
    SleepSession,
)
from aceso.health.infrastructure.models import (
    DailySummaryModel,
    HealthSampleModel,
    SleepSessionModel,
)
from aceso.shared.infrastructure.db import Base

# Keep every statement well below PostgreSQL's 32767 bind-parameter limit.
CHUNK_SIZE = 1000


def _chunks(rows: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(rows), CHUNK_SIZE):
        yield rows[start : start + CHUNK_SIZE]


def _rows(items: Sequence[Any]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        row = asdict(item)
        assert row["user_id"] is not None and row["source"] is not None
        rows.append({k: (v.value if hasattr(v, "value") else v) for k, v in row.items()})
    return rows


class SqlAlchemyHealthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _upsert(
        self,
        model: type[Base],
        rows: list[dict[str, Any]],
        conflict_columns: list[str],
        extra_updates: dict[str, Any] | None = None,
    ) -> None:
        for chunk in _chunks(rows):
            stmt = insert(model).values(chunk)
            updates = {
                column: stmt.excluded[column]
                for column in chunk[0]
                if column not in conflict_columns
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns, set_={**updates, **(extra_updates or {})}
            )
            await self._session.execute(stmt)

    async def upsert_daily_summaries(self, summaries: list[DailySummary]) -> None:
        await self._upsert(
            DailySummaryModel,
            _rows(summaries),
            ["user_id", "day", "source"],
            {"updated_at": func.now()},
        )

    async def upsert_samples(self, samples: list[HealthSample]) -> None:
        await self._upsert(
            HealthSampleModel, _rows(samples), ["user_id", "metric", "recorded_at", "source"]
        )

    async def upsert_sleep_sessions(self, sessions: list[SleepSession]) -> None:
        await self._upsert(SleepSessionModel, _rows(sessions), ["user_id", "source", "start_at"])

    async def list_daily_summaries(
        self, user_id: int, start: date, end: date, source: HealthSource | None
    ) -> list[DailySummary]:
        stmt = select(DailySummaryModel).where(
            DailySummaryModel.user_id == user_id, DailySummaryModel.day.between(start, end)
        )
        if source is not None:
            stmt = stmt.where(DailySummaryModel.source == source.value)
        stmt = stmt.order_by(DailySummaryModel.day, DailySummaryModel.source)
        return [
            DailySummary(
                day=m.day,
                steps=m.steps,
                distance_m=m.distance_m,
                calories_active=m.calories_active,
                calories_total=m.calories_total,
                active_minutes=m.active_minutes,
                resting_hr=m.resting_hr,
                avg_hr=m.avg_hr,
                max_hr=m.max_hr,
                stress_avg=m.stress_avg,
                user_id=m.user_id,
                source=HealthSource(m.source),
            )
            for m in await self._session.scalars(stmt)
        ]

    async def list_samples(
        self,
        user_id: int,
        metric: SampleMetric,
        start: datetime,
        end: datetime,
        source: HealthSource | None,
    ) -> list[HealthSample]:
        stmt = select(HealthSampleModel).where(
            HealthSampleModel.user_id == user_id,
            HealthSampleModel.metric == metric.value,
            HealthSampleModel.recorded_at >= start,
            HealthSampleModel.recorded_at < end,
        )
        if source is not None:
            stmt = stmt.where(HealthSampleModel.source == source.value)
        stmt = stmt.order_by(HealthSampleModel.recorded_at, HealthSampleModel.source)
        return [
            HealthSample(
                metric=SampleMetric(m.metric),
                recorded_at=m.recorded_at,
                value=m.value,
                user_id=m.user_id,
                source=HealthSource(m.source),
            )
            for m in await self._session.scalars(stmt)
        ]

    async def list_sleep_sessions(
        self, user_id: int, start: datetime, end: datetime, source: HealthSource | None
    ) -> list[SleepSession]:
        stmt = select(SleepSessionModel).where(
            SleepSessionModel.user_id == user_id,
            SleepSessionModel.start_at >= start,
            SleepSessionModel.start_at < end,
        )
        if source is not None:
            stmt = stmt.where(SleepSessionModel.source == source.value)
        stmt = stmt.order_by(SleepSessionModel.start_at)
        return [
            SleepSession(
                start_at=m.start_at,
                end_at=m.end_at,
                deep_s=m.deep_s,
                light_s=m.light_s,
                rem_s=m.rem_s,
                awake_s=m.awake_s,
                score=m.score,
                user_id=m.user_id,
                source=HealthSource(m.source),
            )
            for m in await self._session.scalars(stmt)
        ]
