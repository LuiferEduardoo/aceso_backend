from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://aceso:aceso@localhost:5442/aceso"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    fernet_key: str = ""

    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 5 * 1024 * 1024

    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_redirect_uri: str = "http://localhost:8000/running/strava/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
