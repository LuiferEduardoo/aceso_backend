import uuid
from typing import Any

from aceso.gym.domain.entities import Exercise
from aceso.gym.domain.ports import ExerciseRepository
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError
from aceso.shared.domain.storage import FileStorage

ALLOWED_PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MEDIA_TYPE_BY_EXTENSION = {ext: media for media, ext in ALLOWED_PHOTO_TYPES.items()}
UPDATABLE_FIELDS = {"name", "category", "notes"}


class ExerciseService:
    def __init__(self, exercises: ExerciseRepository, storage: FileStorage | None = None) -> None:
        self._exercises = exercises
        self._storage = storage

    async def create(self, exercise: Exercise) -> Exercise:
        return await self._exercises.add(exercise)

    async def list(self, user_id: int) -> list[Exercise]:
        return await self._exercises.list(user_id)

    async def get(self, user_id: int, exercise_id: int) -> Exercise:
        exercise = await self._exercises.get(user_id, exercise_id)
        if exercise is None:
            raise NotFoundError("Exercise not found")
        return exercise

    async def update(self, user_id: int, exercise_id: int, changes: dict[str, Any]) -> Exercise:
        exercise = await self.get(user_id, exercise_id)
        for field, value in changes.items():
            if field in UPDATABLE_FIELDS:
                setattr(exercise, field, value)
        return await self._exercises.update(exercise)

    async def delete(self, user_id: int, exercise_id: int) -> None:
        exercise = await self.get(user_id, exercise_id)
        await self._exercises.delete(exercise)
        if exercise.photo_key:
            await self._require_storage().delete(exercise.photo_key)

    async def set_photo(
        self, user_id: int, exercise_id: int, content_type: str | None, content: bytes
    ) -> Exercise:
        extension = ALLOWED_PHOTO_TYPES.get(content_type or "")
        if extension is None:
            raise InvalidOperationError("Photo must be a JPEG, PNG or WEBP image")
        if not content:
            raise InvalidOperationError("Photo is empty")
        storage = self._require_storage()
        exercise = await self.get(user_id, exercise_id)
        previous_key = exercise.photo_key
        exercise.photo_key = f"exercises/{user_id}/{exercise_id}-{uuid.uuid4().hex}{extension}"
        await storage.save(exercise.photo_key, content)
        exercise = await self._exercises.update(exercise)
        if previous_key:
            await storage.delete(previous_key)
        return exercise

    async def get_photo(self, user_id: int, exercise_id: int) -> tuple[bytes, str]:
        exercise = await self.get(user_id, exercise_id)
        content = (
            await self._require_storage().read(exercise.photo_key) if exercise.photo_key else None
        )
        if exercise.photo_key is None or content is None:
            raise NotFoundError("Exercise has no photo")
        extension = exercise.photo_key[exercise.photo_key.rfind(".") :]
        return content, MEDIA_TYPE_BY_EXTENSION.get(extension, "application/octet-stream")

    async def remove_photo(self, user_id: int, exercise_id: int) -> Exercise:
        exercise = await self.get(user_id, exercise_id)
        if exercise.photo_key:
            key, exercise.photo_key = exercise.photo_key, None
            exercise = await self._exercises.update(exercise)
            await self._require_storage().delete(key)
        return exercise

    def _require_storage(self) -> FileStorage:
        if self._storage is None:
            raise RuntimeError("ExerciseService requires a FileStorage for photo operations")
        return self._storage
