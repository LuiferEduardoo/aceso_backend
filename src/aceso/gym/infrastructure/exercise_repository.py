from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.gym.domain.entities import Exercise, ExerciseCategory
from aceso.gym.infrastructure.models import ExerciseModel
from aceso.shared.domain.errors import ConflictError


def _to_entity(model: ExerciseModel) -> Exercise:
    return Exercise(
        id=model.id,
        user_id=model.user_id,
        name=model.name,
        category=ExerciseCategory(model.category),
        notes=model.notes,
        photo_key=model.photo_key,
        created_at=model.created_at,
    )


class SqlAlchemyExerciseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, exercise: Exercise) -> Exercise:
        model = ExerciseModel(
            user_id=exercise.user_id,
            name=exercise.name,
            category=exercise.category.value,
            notes=exercise.notes,
            photo_key=exercise.photo_key,
        )
        self._session.add(model)
        await self._flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def get(self, user_id: int, exercise_id: int) -> Exercise | None:
        model = await self._get_model(user_id, exercise_id)
        return _to_entity(model) if model else None

    async def list_all(self, user_id: int) -> list[Exercise]:
        stmt = (
            select(ExerciseModel)
            .where(ExerciseModel.user_id == user_id)
            .order_by(ExerciseModel.name, ExerciseModel.id)
        )
        return [_to_entity(m) for m in await self._session.scalars(stmt)]

    async def update(self, exercise: Exercise) -> Exercise:
        assert exercise.id is not None
        model = await self._get_model(exercise.user_id, exercise.id)
        assert model is not None
        model.name = exercise.name
        model.category = ExerciseCategory(exercise.category).value
        model.notes = exercise.notes
        model.photo_key = exercise.photo_key
        await self._flush()
        return _to_entity(model)

    async def delete(self, exercise: Exercise) -> None:
        assert exercise.id is not None
        model = await self._get_model(exercise.user_id, exercise.id)
        if model is not None:
            await self._session.delete(model)
            await self._flush("Exercise is used by routines or sessions")

    async def _get_model(self, user_id: int, exercise_id: int) -> ExerciseModel | None:
        stmt = select(ExerciseModel).where(
            ExerciseModel.id == exercise_id, ExerciseModel.user_id == user_id
        )
        return await self._session.scalar(stmt)

    async def _flush(self, conflict_message: str = "Exercise name already exists") -> None:
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(conflict_message) from exc
