from datetime import UTC, datetime, timedelta

import jwt
import pytest

from aceso.shared.domain.errors import AuthenticationError
from aceso.shared.infrastructure.security import Argon2PasswordHasher, JwtService

SECRET = "x" * 40


def test_jwt_round_trip_and_purpose_check() -> None:
    service = JwtService(SECRET)
    token = service.encode(42, "access", timedelta(minutes=5))
    assert service.decode(token, "access") == 42
    with pytest.raises(AuthenticationError):
        service.decode(token, "strava_oauth_state")


def test_jwt_tolerates_small_clock_skew_but_not_expiry() -> None:
    service = JwtService(SECRET)
    now = datetime.now(UTC)
    skewed = jwt.encode(
        {
            "sub": "1",
            "purpose": "access",
            "iat": now + timedelta(seconds=3),
            "exp": now + timedelta(minutes=1),
        },
        SECRET,
    )
    assert service.decode(skewed, "access") == 1
    expired = service.encode(1, "access", timedelta(minutes=-5))
    with pytest.raises(AuthenticationError):
        service.decode(expired, "access")


def test_password_hasher() -> None:
    hasher = Argon2PasswordHasher()
    password_hash = hasher.hash("password123")
    assert hasher.verify("password123", password_hash)
    assert not hasher.verify("nope", password_hash)
