from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.running.domain.entities import Activity, ActivitySource
from aceso.running.infrastructure.models import ActivityModel

_FIELDS = (
    "external_id",
    "sport_type",
    "name",
    "start_at",
    "distance_m",
    "moving_time_s",
    "elapsed_time_s",
    "elevation_gain_m",
    "avg_hr",
    "max_hr",
    "avg_speed",
    "calories",
    "raw",
)
_CONFLICT_COLUMNS = ["user_id", "source", "external_id"]
CHUNK_SIZE = 500


def _to_entity(model: ActivityModel) -> Activity:
    return Activity(
        id=model.id,
        user_id=model.user_id,
        source=ActivitySource(model.source),
        **{f: getattr(model, f) for f in _FIELDS},
    )


class SqlAlchemyActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, activities: list[Activity]) -> int:
        unique = {(a.source, a.external_id): a for a in activities}
        rows = [
            {
                "user_id": a.user_id,
                "source": ActivitySource(a.source).value,
                **{f: getattr(a, f) for f in _FIELDS},
            }
            for a in unique.values()
        ]
        for start in range(0, len(rows), CHUNK_SIZE):
            stmt = insert(ActivityModel).values(rows[start : start + CHUNK_SIZE])
            stmt = stmt.on_conflict_do_update(
                index_elements=_CONFLICT_COLUMNS,
                set_={
                    **{f: stmt.excluded[f] for f in _FIELDS if f != "external_id"},
                    "updated_at": func.now(),
                },
            )
            await self._session.execute(stmt)
        return len(rows)

    async def get(self, user_id: int, activity_id: int) -> Activity | None:
        stmt = select(ActivityModel).where(
            ActivityModel.id == activity_id, ActivityModel.user_id == user_id
        )
        model = await self._session.scalar(stmt)
        return _to_entity(model) if model else None

    async def list_range(self, user_id: int, start: datetime, end: datetime) -> list[Activity]:
        stmt = (
            select(ActivityModel)
            .where(
                ActivityModel.user_id == user_id,
                ActivityModel.start_at >= start,
                ActivityModel.start_at < end,
            )
            .order_by(ActivityModel.start_at)
        )
        return [_to_entity(m) for m in await self._session.scalars(stmt)]
