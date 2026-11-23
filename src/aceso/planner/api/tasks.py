from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from aceso.identity.api.deps import CurrentUserIdDep
from aceso.planner.api.common import ResourceId, reject_nulls
from aceso.planner.api.deps import TaskServiceDep
from aceso.planner.api.schemas import TaskCreate, TaskRead, TaskUpdate
from aceso.planner.domain.entities import Task, TaskStatus

router = APIRouter(prefix="/planner/tasks", tags=["planner"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate, user_id: CurrentUserIdDep, service: TaskServiceDep
) -> TaskRead:
    task = await service.create(Task(user_id=user_id, **payload.model_dump()))
    return TaskRead.model_validate(task)


@router.get("")
async def list_tasks(
    user_id: CurrentUserIdDep,
    service: TaskServiceDep,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    due_from: Annotated[date | None, Query()] = None,
    due_to: Annotated[date | None, Query()] = None,
) -> list[TaskRead]:
    tasks = await service.list_filtered(user_id, task_status, due_from, due_to)
    return [TaskRead.model_validate(t) for t in tasks]


@router.get("/{task_id}")
async def get_task(
    task_id: ResourceId, user_id: CurrentUserIdDep, service: TaskServiceDep
) -> TaskRead:
    return TaskRead.model_validate(await service.get(user_id, task_id))


@router.patch("/{task_id}")
async def update_task(
    task_id: ResourceId,
    payload: TaskUpdate,
    user_id: CurrentUserIdDep,
    service: TaskServiceDep,
) -> TaskRead:
    changes = payload.model_dump(exclude_unset=True)
    reject_nulls(changes, "title", "status", "priority")
    return TaskRead.model_validate(await service.update(user_id, task_id, changes))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: ResourceId, user_id: CurrentUserIdDep, service: TaskServiceDep
) -> None:
    await service.delete(user_id, task_id)


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: ResourceId, user_id: CurrentUserIdDep, service: TaskServiceDep
) -> TaskRead:
    return TaskRead.model_validate(await service.complete(user_id, task_id))


@router.post("/{task_id}/reopen")
async def reopen_task(
    task_id: ResourceId, user_id: CurrentUserIdDep, service: TaskServiceDep
) -> TaskRead:
    return TaskRead.model_validate(await service.reopen(user_id, task_id))
