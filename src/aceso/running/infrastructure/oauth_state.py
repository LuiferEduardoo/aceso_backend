from datetime import timedelta

from aceso.shared.infrastructure.security import JwtService

STATE_PURPOSE = "strava_oauth_state"
STATE_TTL = timedelta(minutes=10)


class JwtOAuthStateSigner:
    def __init__(self, jwt_service: JwtService) -> None:
        self._jwt = jwt_service

    def issue(self, user_id: int) -> str:
        return self._jwt.encode(user_id, STATE_PURPOSE, STATE_TTL)

    def verify(self, state: str) -> int:
        return self._jwt.decode(state, STATE_PURPOSE)
