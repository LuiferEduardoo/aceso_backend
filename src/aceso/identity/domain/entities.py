from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class User:
    email: str
    password_hash: str
    id: int | None = None
    created_at: datetime | None = None


def normalize_email(email: str) -> str:
    return email.strip().lower()
