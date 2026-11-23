from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.planner.domain.entities import Habit, HabitFrequency, HabitLog
from aceso.planner.infrastructure.models import HabitLogModel, HabitModel

_HABIT_FIELDS = (
    "name",
    "description",
    "weekdays",
    "times_per_week",
    "target_count",
    "unit",
    "start_date",
    "time_of_day",
    "duration_min",
    "timezone",
    "sync_to_calendar",
    "archived_at",
)


def _to_entity(model: HabitModel) -> Habit:
    return Habit(
        id=model.id,
        user_id=model.user_id,
        frequency=HabitFrequency(model.frequency),
        created_at=model.created_at,
        updated_at=model.updated_at,
        **{f: getattr(model, f) for f in _HABIT_FIELDS},
    )


def _apply(model: HabitModel, habit: Habit) -> HabitModel:
    for name in _HABIT_FIELDS:
        setattr(model, name, getattr(habit, name))
    model.weekdays = list(habit.weekdays)
    model.frequency = HabitFrequency(habit.frequency).value
    return model


def _log_entity(model: HabitLogModel) -> HabitLog:
    return HabitLog(
        id=model.id, habit_id=model.habit_id, day=model.day, count=model.count, note=model.note
    )


class SqlAlchemyHabitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, habit: Habit) -> Habit:
        model = _apply(HabitModel(user_id=habit.user_id), habit)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def get(self, user_id: int, habit_id: int) -> Habit | None:
        model = await self._load(user_id, habit_id)
        return _to_entity(model) if model else None

    async def list_all(self, user_id: int, include_archived: bool) -> list[Habit]:
        stmt = select(HabitModel).where(HabitModel.user_id == user_id)
        if not include_archived:
            stmt = stmt.where(HabitModel.archived_at.is_(None))
        stmt = stmt.order_by(HabitModel.name, HabitModel.id)
        return [_to_entity(m) for m in await self._session.scalars(stmt)]

    async def update(self, habit: Habit) -> Habit:
        assert habit.id is not None
        model = await self._load(habit.user_id, habit.id)
        assert model is not None
        _apply(model, habit)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def delete(self, habit: Habit) -> None:
        assert habit.id is not None
        model = await self._load(habit.user_id, habit.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def upsert_log(self, log: HabitLog) -> HabitLog:
        stmt = insert(HabitLogModel).values(
            habit_id=log.habit_id, day=log.day, count=log.count, note=log.note
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["habit_id", "day"],
            set_={"count": stmt.excluded.count, "note": stmt.excluded.note},
        ).returning(HabitLogModel.id)
        log_id = await self._session.scalar(stmt)
        return HabitLog(
            id=log_id, habit_id=log.habit_id, day=log.day, count=log.count, note=log.note
        )

    async def delete_log(self, habit_id: int, day: date) -> bool:
        result = await self._session.execute(
            delete(HabitLogModel)
            .where(HabitLogModel.habit_id == habit_id, HabitLogModel.day == day)
            .returning(HabitLogModel.id)
        )
        return result.first() is not None

    async def list_logs(
        self, habit_id: int, start: date | None = None, end: date | None = None
    ) -> list[HabitLog]:
        stmt = select(HabitLogModel).where(HabitLogModel.habit_id == habit_id)
        if start is not None:
            stmt = stmt.where(HabitLogModel.day >= start)
        if end is not None:
            stmt = stmt.where(HabitLogModel.day <= end)
        stmt = stmt.order_by(HabitLogModel.day)
        return [_log_entity(m) for m in await self._session.scalars(stmt)]

    async def list_user_logs(self, user_id: int, start: date, end: date) -> list[HabitLog]:
        stmt = (
            select(HabitLogModel)
            .join(HabitModel, HabitModel.id == HabitLogModel.habit_id)
            .where(HabitModel.user_id == user_id, HabitLogModel.day.between(start, end))
            .order_by(HabitLogModel.day, HabitLogModel.habit_id)
        )
        return [_log_entity(m) for m in await self._session.scalars(stmt)]

    async def _load(self, user_id: int, habit_id: int) -> HabitModel | None:
        stmt = select(HabitModel).where(HabitModel.id == habit_id, HabitModel.user_id == user_id)
        return await self._session.scalar(stmt)
