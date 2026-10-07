from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from aceso.gym.api.deps import WorkoutSessionServiceDep
from aceso.gym.api.schemas import (
    ExerciseSetIn,
    ExerciseSetRead,
    ExerciseSetUpdate,
    SessionExerciseAdd,
    SessionExerciseRead,
    WorkoutSessionCreate,
    WorkoutSessionRead,
    WorkoutSessionUpdate,
)
from aceso.gym.domain.entities import WorkoutSession
from aceso.identity.api.deps import CurrentUserIdDep
from aceso.shared.domain.errors import InvalidOperationError

sessions_router = APIRouter(prefix="/gym/sessions", tags=["gym"])
session_exercises_router = APIRouter(prefix="/gym/session-exercises", tags=["gym"])
sets_router = APIRouter(prefix="/gym/sets", tags=["gym"])

ResourceId = Annotated[int, Path(ge=1)]


@sessions_router.get("", summary="Calendar: sessions scheduled within a date range")
async def list_sessions(
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    user_id: CurrentUserIdDep,
    service: WorkoutSessionServiceDep,
) -> list[WorkoutSessionRead]:
    sessions = await service.calendar(user_id, start, end)
    return [WorkoutSessionRead.model_validate(s) for s in sessions]


@sessions_router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: WorkoutSessionCreate, user_id: CurrentUserIdDep, service: WorkoutSessionServiceDep
) -> WorkoutSessionRead:
    session = WorkoutSession(
        user_id=user_id,
        exercises=[item.to_entity() for item in payload.exercises],
        **payload.model_dump(exclude={"exercises"}),
    )
    return WorkoutSessionRead.model_validate(await service.create(session))


@sessions_router.get("/{session_id}")
async def get_session(
    session_id: ResourceId, user_id: CurrentUserIdDep, service: WorkoutSessionServiceDep
) -> WorkoutSessionRead:
    return WorkoutSessionRead.model_validate(await service.get(user_id, session_id))


@sessions_router.patch("/{session_id}")
async def update_session(
    session_id: ResourceId,
    payload: WorkoutSessionUpdate,
    user_id: CurrentUserIdDep,
    service: WorkoutSessionServiceDep,
) -> WorkoutSessionRead:
    changes = payload.model_dump(exclude_unset=True)
    for required in ("scheduled_date", "status"):
        if required in changes and changes[required] is None:
            raise InvalidOperationError(f"{required} cannot be null")
    return WorkoutSessionRead.model_validate(await service.update(user_id, session_id, changes))


@sessions_router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: ResourceId, user_id: CurrentUserIdDep, service: WorkoutSessionServiceDep
) -> None:
    await service.delete(user_id, session_id)


@sessions_router.post("/{session_id}/exercises", status_code=status.HTTP_201_CREATED)
async def add_session_exercise(
    session_id: ResourceId,
    payload: SessionExerciseAdd,
    user_id: CurrentUserIdDep,
    service: WorkoutSessionServiceDep,
) -> SessionExerciseRead:
    item = await service.add_exercise(user_id, session_id, payload.exercise_id, payload.notes)
    return SessionExerciseRead.model_validate(item)


@session_exercises_router.delete("/{session_exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_session_exercise(
    session_exercise_id: ResourceId, user_id: CurrentUserIdDep, service: WorkoutSessionServiceDep
) -> None:
    await service.remove_exercise(user_id, session_exercise_id)


@session_exercises_router.post("/{session_exercise_id}/sets", status_code=status.HTTP_201_CREATED)
async def add_set(
    session_exercise_id: ResourceId,
    payload: ExerciseSetIn,
    user_id: CurrentUserIdDep,
    service: WorkoutSessionServiceDep,
) -> ExerciseSetRead:
    exercise_set = await service.add_set(user_id, session_exercise_id, payload.to_entity())
    return ExerciseSetRead.model_validate(exercise_set)


@sets_router.patch("/{set_id}")
async def update_set(
    set_id: ResourceId,
    payload: ExerciseSetUpdate,
    user_id: CurrentUserIdDep,
    service: WorkoutSessionServiceDep,
) -> ExerciseSetRead:
    changes = payload.model_dump(exclude_unset=True, exclude={"intervals"})
    if "completed" in changes and changes["completed"] is None:
        raise InvalidOperationError("completed cannot be null")
    intervals = (
        [i.to_entity() for i in payload.intervals] if payload.intervals is not None else None
    )
    exercise_set = await service.update_set(user_id, set_id, changes, intervals)
    return ExerciseSetRead.model_validate(exercise_set)


@sets_router.delete("/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_set(
    set_id: ResourceId, user_id: CurrentUserIdDep, service: WorkoutSessionServiceDep
) -> None:
    await service.delete_set(user_id, set_id)
