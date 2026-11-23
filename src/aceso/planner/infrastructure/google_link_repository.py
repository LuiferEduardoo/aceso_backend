from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from aceso.planner.domain.entities import GoogleCalendarLink
from aceso.planner.infrastructure.models import GoogleCalendarLinkModel


def _to_entity(model: GoogleCalendarLinkModel) -> GoogleCalendarLink:
    return GoogleCalendarLink(
        id=model.id,
        user_id=model.user_id,
        calendar_id=model.calendar_id,
        sync_token=model.sync_token,
        last_synced_at=model.last_synced_at,
    )


class SqlAlchemyGoogleCalendarLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: int) -> GoogleCalendarLink | None:
        model = await self._load(user_id)
        return _to_entity(model) if model else None

    async def save(self, link: GoogleCalendarLink) -> GoogleCalendarLink:
        model = await self._load(link.user_id)
        if model is None:
            model = GoogleCalendarLinkModel(user_id=link.user_id)
            self._session.add(model)
        model.calendar_id = link.calendar_id
        model.sync_token = link.sync_token
        model.last_synced_at = link.last_synced_at
        await self._session.flush()
        return _to_entity(model)

    async def delete(self, user_id: int) -> None:
        await self._session.execute(
            delete(GoogleCalendarLinkModel).where(GoogleCalendarLinkModel.user_id == user_id)
        )

    async def _load(self, user_id: int) -> GoogleCalendarLinkModel | None:
        stmt = select(GoogleCalendarLinkModel).where(GoogleCalendarLinkModel.user_id == user_id)
        return await self._session.scalar(stmt)
