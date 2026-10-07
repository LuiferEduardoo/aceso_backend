from typing import Annotated

from fastapi import APIRouter, Path, status

from aceso.gym.api.deps import RoutineServiceDep
from aceso.gym.api.schemas import RoutineCreate, RoutineRead, RoutineUpdate
from aceso.gym.domain.entities import Routine
from aceso.identity.api.deps import CurrentUserIdDep
from aceso.shared.domain.errors import InvalidOperationError

router = APIRouter(prefix="/gym/routines", tags=["gym"])

RoutineId = Annotated[int, Path(ge=1)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_routine(
    payload: RoutineCreate, user_id: CurrentUserIdDep, service: RoutineServiceDep
) -> RoutineRead:
    routine = Routine(
        user_id=user_id,
        name=payload.name,
        description=payload.description,
        exercises=[item.to_entity() for item in payload.exercises],
    )
    return RoutineRead.from_entity(await service.create(routine))


@router.get("")
async def list_routines(user_id: CurrentUserIdDep, service: RoutineServiceDep) -> list[RoutineRead]:
    return [RoutineRead.from_entity(r) for r in await service.list_all(user_id)]


@router.get("/{routine_id}")
async def get_routine(
    routine_id: RoutineId, user_id: CurrentUserIdDep, service: RoutineServiceDep
) -> RoutineRead:
    return RoutineRead.from_entity(await service.get(user_id, routine_id))


@router.patch("/{routine_id}")
async def update_routine(
    routine_id: RoutineId,
    payload: RoutineUpdate,
    user_id: CurrentUserIdDep,
    service: RoutineServiceDep,
) -> RoutineRead:
    if "name" in payload.model_fields_set and payload.name is None:
        raise InvalidOperationError("name cannot be null")
    routine = await service.update(
        user_id,
        routine_id,
        name=payload.name,
        description=payload.description,
        clear_description="description" in payload.model_fields_set,
        exercises=(
            [item.to_entity() for item in payload.exercises]
            if payload.exercises is not None
            else None
        ),
    )
    return RoutineRead.from_entity(routine)


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routine(
    routine_id: RoutineId, user_id: CurrentUserIdDep, service: RoutineServiceDep
) -> None:
    await service.delete(user_id, routine_id)
