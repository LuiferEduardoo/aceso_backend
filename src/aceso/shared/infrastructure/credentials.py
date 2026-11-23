from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from aceso.shared.domain.credentials import IntegrationProvider
from aceso.shared.infrastructure.crypto import FernetCipher
from aceso.shared.infrastructure.db import Base, IdMixin, TimestampMixin


class IntegrationCredentialModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "integration_credentials"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), sort_order=11
    )

    __table_args__ = (
        # The (user_id, provider) unique index also serves the user_id foreign key.
        UniqueConstraint("user_id", "provider"),
        CheckConstraint("provider IN ('garmin', 'strava', 'google')", name="provider"),
    )


class SqlAlchemyCredentialStore:
    def __init__(self, session: AsyncSession, cipher: FernetCipher) -> None:
        self._session = session
        self._cipher = cipher

    async def get(self, user_id: int, provider: IntegrationProvider) -> dict[str, Any] | None:
        stmt = select(IntegrationCredentialModel.encrypted_payload).where(
            IntegrationCredentialModel.user_id == user_id,
            IntegrationCredentialModel.provider == provider.value,
        )
        encrypted = await self._session.scalar(stmt)
        return self._cipher.decrypt_json(encrypted) if encrypted else None

    async def save(
        self, user_id: int, provider: IntegrationProvider, payload: dict[str, Any]
    ) -> None:
        encrypted = self._cipher.encrypt_json(payload)
        stmt = insert(IntegrationCredentialModel).values(
            user_id=user_id, provider=provider.value, encrypted_payload=encrypted
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "provider"],
            set_={"encrypted_payload": encrypted, "updated_at": func.now()},
        )
        await self._session.execute(stmt)

    async def delete(self, user_id: int, provider: IntegrationProvider) -> None:
        await self._session.execute(
            delete(IntegrationCredentialModel).where(
                IntegrationCredentialModel.user_id == user_id,
                IntegrationCredentialModel.provider == provider.value,
            )
        )
