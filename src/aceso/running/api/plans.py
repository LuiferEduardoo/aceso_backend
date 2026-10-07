from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status

from aceso.identity.api.deps import CurrentUserIdDep
from aceso.running.api.deps import TrainingPlanServiceDep
from aceso.running.api.schemas import (
    PlannedRunIn,
    PlannedRunRead,
    PlannedRunUpdate,
    TrainingPlanCreate,
    TrainingPlanRead,
    TrainingPlanUpdate,
)
from aceso.running.domain.entities import TrainingPlan
from aceso.shared.domain.errors import InvalidOperationError

plans_router = APIRouter(prefix="/running/plans", tags=["running"])
planned_runs_router = APIRouter(prefix="/running/planned-runs", tags=["running"])

ResourceId = Annotated[int, Path(ge=1)]


def _reject_nulls(changes: dict[str, Any], *fields: str) -> None:
    for name in fields:
        if name in changes and changes[name] is None:
            raise InvalidOperationError(f"{name} cannot be null")


@plans_router.post("", status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: TrainingPlanCreate, user_id: CurrentUserIdDep, service: TrainingPlanServiceDep
) -> TrainingPlanRead:
    plan = TrainingPlan(
        user_id=user_id,
        runs=[run.to_entity() for run in payload.runs],
        **payload.model_dump(exclude={"runs"}),
    )
    return TrainingPlanRead.model_validate(await service.create(plan))


@plans_router.get("")
async def list_plans(
    user_id: CurrentUserIdDep, service: TrainingPlanServiceDep
) -> list[TrainingPlanRead]:
    return [TrainingPlanRead.model_validate(p) for p in await service.list_all(user_id)]


@plans_router.get("/{plan_id}")
async def get_plan(
    plan_id: ResourceId, user_id: CurrentUserIdDep, service: TrainingPlanServiceDep
) -> TrainingPlanRead:
    return TrainingPlanRead.model_validate(await service.get(user_id, plan_id))


@plans_router.patch("/{plan_id}")
async def update_plan(
    plan_id: ResourceId,
    payload: TrainingPlanUpdate,
    user_id: CurrentUserIdDep,
    service: TrainingPlanServiceDep,
) -> TrainingPlanRead:
    changes = payload.model_dump(exclude_unset=True)
    _reject_nulls(changes, "name", "start_date", "end_date")
    return TrainingPlanRead.model_validate(await service.update(user_id, plan_id, changes))


@plans_router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: ResourceId, user_id: CurrentUserIdDep, service: TrainingPlanServiceDep
) -> None:
    await service.delete(user_id, plan_id)


@plans_router.post("/{plan_id}/runs", status_code=status.HTTP_201_CREATED)
async def add_planned_run(
    plan_id: ResourceId,
    payload: PlannedRunIn,
    user_id: CurrentUserIdDep,
    service: TrainingPlanServiceDep,
) -> PlannedRunRead:
    run = await service.add_run(user_id, plan_id, payload.to_entity())
    return PlannedRunRead.model_validate(run)


@planned_runs_router.get("", summary="Planned runs (all plans) within a date range")
async def list_planned_runs(
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    user_id: CurrentUserIdDep,
    service: TrainingPlanServiceDep,
) -> list[PlannedRunRead]:
    runs = await service.runs_between(user_id, start, end)
    return [PlannedRunRead.model_validate(r) for r in runs]


@planned_runs_router.patch("/{run_id}")
async def update_planned_run(
    run_id: ResourceId,
    payload: PlannedRunUpdate,
    user_id: CurrentUserIdDep,
    service: TrainingPlanServiceDep,
) -> PlannedRunRead:
    changes = payload.model_dump(exclude_unset=True)
    _reject_nulls(changes, "scheduled_date", "run_type")
    return PlannedRunRead.model_validate(await service.update_run(user_id, run_id, changes))


@planned_runs_router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_planned_run(
    run_id: ResourceId, user_id: CurrentUserIdDep, service: TrainingPlanServiceDep
) -> None:
    await service.delete_run(user_id, run_id)
