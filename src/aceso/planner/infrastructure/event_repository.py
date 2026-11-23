from datetime import datetime

from sqlalchemy import ColumnElement, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.planner.domain.entities import CalendarEvent, EventSource
from aceso.planner.infrastructure.models import CalendarEventModel

_FIELDS = (
    "title",
    "description",
    "location",
    "start_at",
    "end_at",
    "all_day",
    "task_id",
    "habit_id",
    "google_event_id",
    "etag",
    "remote_updated_at",
    "sync_pending",
    "deleted_at",
)


def _to_entity(model: CalendarEventModel) -> CalendarEvent:
    return CalendarEvent(
        id=model.id,
        user_id=model.user_id,
        source=EventSource(model.source),
        created_at=model.created_at,
        updated_at=model.updated_at,
        **{f: getattr(model, f) for f in _FIELDS},
    )


def _apply(model: CalendarEventModel, event: CalendarEvent) -> CalendarEventModel:
    for name in _FIELDS:
        setattr(model, name, getattr(event, name))
    model.source = EventSource(event.source).value
    return model


class SqlAlchemyCalendarEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: CalendarEvent) -> CalendarEvent:
        model = _apply(CalendarEventModel(user_id=event.user_id), event)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def get(self, user_id: int, event_id: int) -> CalendarEvent | None:
        return await self._one(
            CalendarEventModel.user_id == user_id,
            CalendarEventModel.id == event_id,
            CalendarEventModel.deleted_at.is_(None),
        )

    async def get_by_task(self, user_id: int, task_id: int) -> CalendarEvent | None:
        return await self._one(
            CalendarEventModel.user_id == user_id,
            CalendarEventModel.task_id == task_id,
            CalendarEventModel.deleted_at.is_(None),
        )

    async def list_range(self, user_id: int, start: datetime, end: datetime) -> list[CalendarEvent]:
        stmt = (
            select(CalendarEventModel)
            .where(
                CalendarEventModel.user_id == user_id,
                CalendarEventModel.deleted_at.is_(None),
                CalendarEventModel.start_at < end,
                CalendarEventModel.end_at > start,
            )
            .order_by(CalendarEventModel.start_at, CalendarEventModel.id)
        )
        return [_to_entity(m) for m in await self._session.scalars(stmt)]

    async def update(self, event: CalendarEvent) -> CalendarEvent:
        assert event.id is not None
        model = await self._session.get(CalendarEventModel, event.id)
        assert model is not None and model.user_id == event.user_id
        _apply(model, event)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def delete(self, event: CalendarEvent) -> None:
        model = await self._session.get(CalendarEventModel, event.id)
        if model is not None and model.user_id == event.user_id:
            await self._session.delete(model)
            await self._session.flush()

    async def get_by_google_id(self, user_id: int, google_event_id: str) -> CalendarEvent | None:
        return await self._one(
            CalendarEventModel.user_id == user_id,
            CalendarEventModel.google_event_id == google_event_id,
        )

    async def list_synced_between(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        stmt = select(CalendarEventModel).where(
            CalendarEventModel.user_id == user_id,
            CalendarEventModel.deleted_at.is_(None),
            CalendarEventModel.google_event_id.is_not(None),
            CalendarEventModel.habit_id.is_(None),
            CalendarEventModel.sync_pending.is_(False),
            CalendarEventModel.start_at >= start,
            CalendarEventModel.start_at < end,
        )
        return [_to_entity(m) for m in await self._session.scalars(stmt)]

    async def habit_google_ids(self, user_id: int) -> set[str]:
        stmt = select(CalendarEventModel.google_event_id).where(
            CalendarEventModel.user_id == user_id,
            CalendarEventModel.habit_id.is_not(None),
            CalendarEventModel.google_event_id.is_not(None),
        )
        return {gid for gid in await self._session.scalars(stmt) if gid}

    async def reset_sync(self, user_id: int) -> None:
        await self._session.execute(
            delete(CalendarEventModel).where(
                CalendarEventModel.user_id == user_id,
                or_(
                    CalendarEventModel.source == EventSource.GOOGLE.value,
                    CalendarEventModel.deleted_at.is_not(None),
                ),
            )
        )
        await self._session.execute(
            update(CalendarEventModel)
            .where(CalendarEventModel.user_id == user_id)
            .values(google_event_id=None, etag=None, remote_updated_at=None, sync_pending=True)
        )
        self._session.expire_all()

    async def _one(self, *conditions: ColumnElement[bool]) -> CalendarEvent | None:
        model = await self._session.scalar(select(CalendarEventModel).where(*conditions))
        return _to_entity(model) if model else None
