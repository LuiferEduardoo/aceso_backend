from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.gym.domain.entities import Routine, RoutineExercise
from aceso.gym.infrastructure.models import RoutineExerciseModel, RoutineModel

_ITEM_FIELDS = (
    "exercise_id",
    "position",
    "target_sets",
    "target_reps",
    "target_weight_kg",
    "target_duration_s",
    "notes",
)


def _to_entity(model: RoutineModel) -> Routine:
    return Routine(
        id=model.id,
        user_id=model.user_id,
        name=model.name,
        description=model.description,
        created_at=model.created_at,
        exercises=[
            RoutineExercise(id=item.id, **{f: getattr(item, f) for f in _ITEM_FIELDS})
            for item in model.items
        ],
    )


def _to_item_model(item: RoutineExercise) -> RoutineExerciseModel:
    return RoutineExerciseModel(**{f: getattr(item, f) for f in _ITEM_FIELDS})


class SqlAlchemyRoutineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, routine: Routine) -> Routine:
        model = RoutineModel(
            user_id=routine.user_id,
            name=routine.name,
            description=routine.description,
            items=[_to_item_model(item) for item in routine.exercises],
        )
        self._session.add(model)
        await self._session.flush()
        return await self._reload(model)

    async def get(self, user_id: int, routine_id: int) -> Routine | None:
        model = await self._get_model(user_id, routine_id)
        return _to_entity(model) if model else None

    async def list_all(self, user_id: int) -> list[Routine]:
        stmt = (
            select(RoutineModel)
            .where(RoutineModel.user_id == user_id)
            .order_by(RoutineModel.name, RoutineModel.id)
        )
        return [_to_entity(m) for m in await self._session.scalars(stmt)]

    async def update(self, routine: Routine) -> Routine:
        assert routine.id is not None
        model = await self._get_model(routine.user_id, routine.id)
        assert model is not None
        model.name = routine.name
        model.description = routine.description
        # Delete old rows first so (routine_id, position) stays unique.
        model.items.clear()
        await self._session.flush()
        model.items.extend(_to_item_model(item) for item in routine.exercises)
        await self._session.flush()
        return await self._reload(model)

    async def delete(self, routine: Routine) -> None:
        assert routine.id is not None
        model = await self._get_model(routine.user_id, routine.id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    async def _get_model(self, user_id: int, routine_id: int) -> RoutineModel | None:
        stmt = select(RoutineModel).where(
            RoutineModel.id == routine_id, RoutineModel.user_id == user_id
        )
        return await self._session.scalar(stmt)

    async def _reload(self, model: RoutineModel) -> Routine:
        stmt = (
            select(RoutineModel)
            .where(RoutineModel.id == model.id)
            .execution_options(populate_existing=True)
        )
        return _to_entity((await self._session.scalars(stmt)).one())
