from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status

from aceso.identity.api.deps import CurrentUserIdDep
from aceso.planner.api.deps import HabitServiceDep, HabitTrackingDep
from aceso.planner.api.schemas import (
    HabitCreate,
    HabitLogIn,
    HabitLogRead,
    HabitRead,
    HabitStatsRead,
    HabitUpdate,
)
from aceso.planner.domain.entities import Habit
from aceso.shared.domain.errors import InvalidOperationError

router = APIRouter(prefix="/planner/habits", tags=["planner"])

ResourceId = Annotated[int, Path(ge=1)]


def reject_nulls(changes: dict[str, Any], *fields: str) -> None:
    for name in fields:
        if name in changes and changes[name] is None:
            raise InvalidOperationError(f"{name} cannot be null")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_habit(
    payload: HabitCreate, user_id: CurrentUserIdDep, service: HabitServiceDep
) -> HabitRead:
    habit = await service.create(Habit(user_id=user_id, **payload.model_dump()))
    return HabitRead.model_validate(habit)


@router.get("")
async def list_habits(
    user_id: CurrentUserIdDep,
    service: HabitServiceDep,
    include_archived: Annotated[bool, Query()] = False,
) -> list[HabitRead]:
    habits = await service.list_all(user_id, include_archived)
    return [HabitRead.model_validate(h) for h in habits]


@router.get("/{habit_id}")
async def get_habit(
    habit_id: ResourceId, user_id: CurrentUserIdDep, service: HabitServiceDep
) -> HabitRead:
    return HabitRead.model_validate(await service.get(user_id, habit_id))


@router.patch("/{habit_id}")
async def update_habit(
    habit_id: ResourceId,
    payload: HabitUpdate,
    user_id: CurrentUserIdDep,
    service: HabitServiceDep,
) -> HabitRead:
    changes = payload.model_dump(exclude_unset=True)
    reject_nulls(
        changes,
        "name",
        "frequency",
        "weekdays",
        "target_count",
        "start_date",
        "timezone",
        "sync_to_calendar",
    )
    return HabitRead.model_validate(await service.update(user_id, habit_id, changes))


@router.delete("/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_habit(
    habit_id: ResourceId, user_id: CurrentUserIdDep, service: HabitServiceDep
) -> None:
    await service.delete(user_id, habit_id)


@router.post("/{habit_id}/archive")
async def archive_habit(
    habit_id: ResourceId, user_id: CurrentUserIdDep, service: HabitServiceDep
) -> HabitRead:
    return HabitRead.model_validate(await service.archive(user_id, habit_id))


@router.post("/{habit_id}/unarchive")
async def unarchive_habit(
    habit_id: ResourceId, user_id: CurrentUserIdDep, service: HabitServiceDep
) -> HabitRead:
    return HabitRead.model_validate(await service.unarchive(user_id, habit_id))


@router.get("/{habit_id}/logs")
async def list_habit_logs(
    habit_id: ResourceId,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    user_id: CurrentUserIdDep,
    tracking: HabitTrackingDep,
) -> list[HabitLogRead]:
    logs = await tracking.logs(user_id, habit_id, start, end)
    return [HabitLogRead.model_validate(log) for log in logs]


@router.post("/{habit_id}/logs/{day}", summary="Check in a day (replaces an existing log)")
async def log_habit_day(
    habit_id: ResourceId,
    day: date,
    user_id: CurrentUserIdDep,
    tracking: HabitTrackingDep,
    payload: HabitLogIn | None = None,
) -> HabitLogRead:
    payload = payload or HabitLogIn()
    log = await tracking.log(user_id, habit_id, day, payload.count, payload.note)
    return HabitLogRead.model_validate(log)


@router.delete("/{habit_id}/logs/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def unlog_habit_day(
    habit_id: ResourceId, day: date, user_id: CurrentUserIdDep, tracking: HabitTrackingDep
) -> None:
    await tracking.unlog(user_id, habit_id, day)


@router.get("/{habit_id}/stats")
async def habit_stats(
    habit_id: ResourceId,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    user_id: CurrentUserIdDep,
    tracking: HabitTrackingDep,
) -> HabitStatsRead:
    stats = await tracking.stats(user_id, habit_id, start, end)
    return HabitStatsRead.model_validate(stats)
