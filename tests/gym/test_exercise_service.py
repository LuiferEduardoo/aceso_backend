import pytest

from aceso.gym.application.exercises import ExerciseService
from aceso.gym.domain.entities import Exercise, ExerciseCategory
from aceso.shared.domain.errors import InvalidOperationError, NotFoundError
from tests.gym.fakes import FakeExerciseRepository, FakeStorage


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def service(storage: FakeStorage) -> ExerciseService:
    return ExerciseService(FakeExerciseRepository(), storage)


async def test_exercises_are_scoped_to_their_owner(service: ExerciseService) -> None:
    created = await service.create(Exercise(user_id=1, name="Squat"))
    assert created.id is not None
    with pytest.raises(NotFoundError):
        await service.get(2, created.id)
    assert await service.list(2) == []


async def test_update_only_touches_allowed_fields(service: ExerciseService) -> None:
    created = await service.create(Exercise(user_id=1, name="Squat"))
    assert created.id is not None
    updated = await service.update(
        1, created.id, {"name": "Back squat", "category": ExerciseCategory.OTHER, "user_id": 9}
    )
    assert updated.name == "Back squat"
    assert updated.category == ExerciseCategory.OTHER
    assert updated.user_id == 1


async def test_set_photo_replaces_previous_file(
    service: ExerciseService, storage: FakeStorage
) -> None:
    created = await service.create(Exercise(user_id=1, name="Stair climber"))
    assert created.id is not None
    first = await service.set_photo(1, created.id, "image/png", b"one")
    second = await service.set_photo(1, created.id, "image/jpeg", b"two")
    assert first.photo_key and second.photo_key
    assert first.photo_key not in storage.files
    assert await service.get_photo(1, created.id) == (b"two", "image/jpeg")


async def test_set_photo_rejects_non_images(service: ExerciseService) -> None:
    created = await service.create(Exercise(user_id=1, name="Bench"))
    assert created.id is not None
    with pytest.raises(InvalidOperationError):
        await service.set_photo(1, created.id, "application/pdf", b"%PDF")


async def test_delete_removes_photo(service: ExerciseService, storage: FakeStorage) -> None:
    created = await service.create(Exercise(user_id=1, name="Bench"))
    assert created.id is not None
    await service.set_photo(1, created.id, "image/png", b"img")
    await service.delete(1, created.id)
    assert storage.files == {}
    with pytest.raises(NotFoundError):
        await service.get(1, created.id)
