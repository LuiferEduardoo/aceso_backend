import pytest

from aceso.shared.domain.errors import AuthenticationError
from aceso.shared.infrastructure.oauth_state import JwtOAuthStateSigner
from aceso.shared.infrastructure.security import JwtService

SECRET = "x" * 40


def test_state_round_trip_is_bound_to_purpose() -> None:
    jwt_service = JwtService(SECRET)
    strava = JwtOAuthStateSigner(jwt_service, "strava_oauth_state")
    google = JwtOAuthStateSigner(jwt_service, "google_oauth_state")

    state = strava.issue(7)

    assert strava.verify(state) == 7
    with pytest.raises(AuthenticationError):
        google.verify(state)
