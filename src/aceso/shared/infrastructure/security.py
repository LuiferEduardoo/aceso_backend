from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from aceso.shared.domain.errors import AuthenticationError

# Tolerate small clock differences (PyJWT rejects tokens whose `iat` is in the future).
CLOCK_LEEWAY = timedelta(seconds=10)


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._hasher.verify(password, password_hash)


class JwtService:
    """Signs and verifies short-lived JWTs (access tokens, OAuth state)."""

    def __init__(self, secret: str, algorithm: str = "HS256") -> None:
        self._secret = secret
        self._algorithm = algorithm

    def encode(self, subject: int, purpose: str, expires_in: timedelta) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": str(subject),
            "purpose": purpose,
            "iat": now,
            "exp": now + expires_in,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode(self, token: str, purpose: str) -> int:
        """Return the subject id or raise AuthenticationError."""
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=[self._algorithm], leeway=CLOCK_LEEWAY
            )
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Invalid or expired token") from exc
        if payload.get("purpose") != purpose or not str(payload.get("sub", "")).isdigit():
            raise AuthenticationError("Invalid token")
        return int(payload["sub"])
