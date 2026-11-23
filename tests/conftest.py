import os
import tempfile
from collections.abc import AsyncIterator

import pytest
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


class _TestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    test_database_url: str = "postgresql+asyncpg://aceso:aceso@localhost:5442/aceso_test"


# Configure the app for tests before any aceso module reads the settings.
os.environ["DATABASE_URL"] = _TestSettings().test_database_url
os.environ["JWT_SECRET"] = "test-secret-not-for-production-0123456789"
os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["STORAGE_BACKEND"] = "local"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="aceso-test-uploads-")
os.environ["STRAVA_CLIENT_ID"] = "test-client-id"
os.environ["STRAVA_CLIENT_SECRET"] = "test-client-secret"
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-google-client-secret"

from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

import aceso.models  # noqa: E402, F401
from aceso.main import create_app  # noqa: E402
from aceso.shared.config import get_settings  # noqa: E402
from aceso.shared.infrastructure.db import Base, get_session  # noqa: E402


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sessionmaker(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield async_sessionmaker(engine, expire_on_commit=False)
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    if tables:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def app(sessionmaker: async_sessionmaker[AsyncSession]) -> FastAPI:
    app = create_app()

    async def _get_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _get_session
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def register_and_login(client: AsyncClient, email: str) -> dict[str, str]:
    """Create a user and return the Authorization header for it."""
    password = "s3cret-password"
    response = await client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    response = await client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    client.headers.update(await register_and_login(client, "athlete@example.com"))
    return client
