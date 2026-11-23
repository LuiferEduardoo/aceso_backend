from datetime import timedelta

from aceso.shared.infrastructure.security import JwtService

STATE_TTL = timedelta(minutes=10)


class JwtOAuthStateSigner:
    """Signs an OAuth `state` bound to a user; `purpose` keeps providers' states apart."""

    def __init__(self, jwt_service: JwtService, purpose: str) -> None:
        self._jwt = jwt_service
        self._purpose = purpose

    def issue(self, user_id: int) -> str:
        return self._jwt.encode(user_id, self._purpose, STATE_TTL)

    def verify(self, state: str) -> int:
        return self._jwt.decode(state, self._purpose)
