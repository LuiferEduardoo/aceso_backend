from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.identity.domain.entities import User
from aceso.identity.infrastructure.models import UserModel


def _to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        created_at=model.created_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return _to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(func.lower(UserModel.email) == email.lower())
        model = await self._session.scalar(stmt)
        return _to_entity(model) if model else None

    async def add(self, user: User) -> User:
        model = UserModel(email=user.email, password_hash=user.password_hash)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)
