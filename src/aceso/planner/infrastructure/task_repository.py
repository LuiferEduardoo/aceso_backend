from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.planner.domain.entities import Task, TaskPriority, TaskStatus
from aceso.planner.infrastructure.models import TaskModel

_FIELDS = (
    "title",
    "notes",
    "due_date",
    "scheduled_start",
    "scheduled_end",
    "completed_at",
)


def to_task_entity(model: TaskModel) -> Task:
    return Task(
        id=model.id,
        user_id=model.user_id,
        status=TaskStatus(model.status),
        priority=TaskPriority(model.priority),
        created_at=model.created_at,
        updated_at=model.updated_at,
        **{f: getattr(model, f) for f in _FIELDS},
    )


def _apply(model: TaskModel, task: Task) -> TaskModel:
    for name in _FIELDS:
        setattr(model, name, getattr(task, name))
    model.status = TaskStatus(task.status).value
    model.priority = TaskPriority(task.priority).value
    return model


class SqlAlchemyTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: Task) -> Task:
        model = _apply(TaskModel(user_id=task.user_id), task)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return to_task_entity(model)

    async def get(self, user_id: int, task_id: int) -> Task | None:
        model = await self._load(user_id, task_id)
        return to_task_entity(model) if model else None

    async def list_filtered(
        self,
        user_id: int,
        status: TaskStatus | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
    ) -> list[Task]:
        stmt = select(TaskModel).where(TaskModel.user_id == user_id)
        if status is not None:
            stmt = stmt.where(TaskModel.status == TaskStatus(status).value)
        if due_from is not None:
            stmt = stmt.where(TaskModel.due_date >= due_from)
        if due_to is not None:
            stmt = stmt.where(TaskModel.due_date <= due_to)
        stmt = stmt.order_by(TaskModel.due_date.asc().nulls_last(), TaskModel.id)
        return [to_task_entity(m) for m in await self._session.scalars(stmt)]

    async def update(self, task: Task) -> Task:
        assert task.id is not None
        model = await self._load(task.user_id, task.id)
        assert model is not None
        _apply(model, task)
        await self._session.flush()
        await self._session.refresh(model)
        return to_task_entity(model)

    async def delete(self, task: Task) -> None:
        assert task.id is not None
        model = await self._load(task.user_id, task.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def _load(self, user_id: int, task_id: int) -> TaskModel | None:
        stmt = select(TaskModel).where(TaskModel.id == task_id, TaskModel.user_id == user_id)
        return await self._session.scalar(stmt)
