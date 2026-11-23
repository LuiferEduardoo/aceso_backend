import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aceso.identity.infrastructure.models import UserModel
from aceso.shared.domain.credentials import IntegrationProvider
from aceso.shared.domain.errors import IntegrationError
from aceso.shared.infrastructure.credentials import (
    IntegrationCredentialModel,
    SqlAlchemyCredentialStore,
)
from aceso.shared.infrastructure.crypto import FernetCipher


def test_cipher_round_trip_and_wrong_key() -> None:
    cipher = FernetCipher(Fernet.generate_key().decode())
    token = cipher.encrypt_json({"access_token": "abc"})
    assert "abc" not in token
    assert cipher.decrypt_json(token) == {"access_token": "abc"}
    with pytest.raises(IntegrationError):
        FernetCipher(Fernet.generate_key().decode()).decrypt_json(token)
    with pytest.raises(IntegrationError):
        FernetCipher("")


async def test_store_upserts_encrypted_payload(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    cipher = FernetCipher(Fernet.generate_key().decode())
    async with sessionmaker() as session:
        user = UserModel(email="c@example.com", password_hash="x")
        session.add(user)
        await session.flush()
        store = SqlAlchemyCredentialStore(session, cipher)

        await store.save(user.id, IntegrationProvider.STRAVA, {"refresh_token": "r1"})
        await store.save(user.id, IntegrationProvider.STRAVA, {"refresh_token": "r2"})
        assert await store.get(user.id, IntegrationProvider.STRAVA) == {"refresh_token": "r2"}
        assert await store.get(user.id, IntegrationProvider.GARMIN) is None

        raw = await session.scalar(select(IntegrationCredentialModel.encrypted_payload))
        assert raw is not None and "r2" not in raw

        await store.delete(user.id, IntegrationProvider.STRAVA)
        assert await store.get(user.id, IntegrationProvider.STRAVA) is None


async def test_store_accepts_google_provider(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    cipher = FernetCipher(Fernet.generate_key().decode())
    async with sessionmaker() as session:
        user = UserModel(email="g@example.com", password_hash="x")
        session.add(user)
        await session.flush()
        store = SqlAlchemyCredentialStore(session, cipher)

        await store.save(user.id, IntegrationProvider.GOOGLE, {"refresh_token": "g1"})
        await session.commit()
        assert await store.get(user.id, IntegrationProvider.GOOGLE) == {"refresh_token": "g1"}
