from typing import Annotated

from fastapi import APIRouter, File, Path, Response, UploadFile, status

from aceso.gym.api.deps import ExerciseServiceDep
from aceso.gym.api.schemas import ExerciseCreate, ExerciseRead, ExerciseUpdate
from aceso.gym.domain.entities import Exercise
from aceso.identity.api.deps import CurrentUserIdDep
from aceso.shared.api.deps import SettingsDep
from aceso.shared.domain.errors import InvalidOperationError

router = APIRouter(prefix="/gym/exercises", tags=["gym"])

ExerciseId = Annotated[int, Path(ge=1)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_exercise(
    payload: ExerciseCreate, user_id: CurrentUserIdDep, service: ExerciseServiceDep
) -> ExerciseRead:
    exercise = await service.create(Exercise(user_id=user_id, **payload.model_dump()))
    return ExerciseRead.from_entity(exercise)


@router.get("")
async def list_exercises(
    user_id: CurrentUserIdDep, service: ExerciseServiceDep
) -> list[ExerciseRead]:
    return [ExerciseRead.from_entity(e) for e in await service.list_all(user_id)]


@router.get("/{exercise_id}")
async def get_exercise(
    exercise_id: ExerciseId, user_id: CurrentUserIdDep, service: ExerciseServiceDep
) -> ExerciseRead:
    return ExerciseRead.from_entity(await service.get(user_id, exercise_id))


@router.patch("/{exercise_id}")
async def update_exercise(
    exercise_id: ExerciseId,
    payload: ExerciseUpdate,
    user_id: CurrentUserIdDep,
    service: ExerciseServiceDep,
) -> ExerciseRead:
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise InvalidOperationError("name cannot be null")
    if "category" in changes and changes["category"] is None:
        raise InvalidOperationError("category cannot be null")
    return ExerciseRead.from_entity(await service.update(user_id, exercise_id, changes))


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exercise(
    exercise_id: ExerciseId, user_id: CurrentUserIdDep, service: ExerciseServiceDep
) -> None:
    await service.delete(user_id, exercise_id)


@router.put("/{exercise_id}/photo")
async def upload_exercise_photo(
    exercise_id: ExerciseId,
    photo: Annotated[UploadFile, File()],
    user_id: CurrentUserIdDep,
    service: ExerciseServiceDep,
    settings: SettingsDep,
) -> ExerciseRead:
    content = await photo.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise InvalidOperationError("Photo is too large")
    exercise = await service.set_photo(user_id, exercise_id, photo.content_type, content)
    return ExerciseRead.from_entity(exercise)


@router.get("/{exercise_id}/photo", response_class=Response)
async def get_exercise_photo(
    exercise_id: ExerciseId, user_id: CurrentUserIdDep, service: ExerciseServiceDep
) -> Response:
    content, media_type = await service.get_photo(user_id, exercise_id)
    return Response(content=content, media_type=media_type)


@router.delete("/{exercise_id}/photo")
async def delete_exercise_photo(
    exercise_id: ExerciseId, user_id: CurrentUserIdDep, service: ExerciseServiceDep
) -> ExerciseRead:
    return ExerciseRead.from_entity(await service.remove_photo(user_id, exercise_id))
