from datetime import timedelta

from aceso.shared.infrastructure.security import JwtService

ACCESS_TOKEN_PURPOSE = "access"


class JwtAccessTokenIssuer:
    def __init__(self, jwt_service: JwtService, expire_minutes: int) -> None:
        self._jwt = jwt_service
        self._expires_in = timedelta(minutes=expire_minutes)

    def issue(self, user_id: int) -> str:
        return self._jwt.encode(user_id, ACCESS_TOKEN_PURPOSE, self._expires_in)

    def verify(self, token: str) -> int:
        return self._jwt.decode(token, ACCESS_TOKEN_PURPOSE)
