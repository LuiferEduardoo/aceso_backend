from aceso.identity.domain.entities import User, normalize_email
from aceso.identity.domain.ports import AccessTokenIssuer, PasswordHasher, UserRepository
from aceso.shared.domain.errors import AuthenticationError, ConflictError, NotFoundError


class RegisterUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher) -> None:
        self._users = users
        self._hasher = hasher

    async def execute(self, email: str, password: str) -> User:
        email = normalize_email(email)
        if await self._users.get_by_email(email) is not None:
            raise ConflictError("Email already registered")
        return await self._users.add(User(email=email, password_hash=self._hasher.hash(password)))


class LoginUser:
    def __init__(
        self, users: UserRepository, hasher: PasswordHasher, tokens: AccessTokenIssuer
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    async def execute(self, email: str, password: str) -> str:
        user = await self._users.get_by_email(normalize_email(email))
        if user is None or not self._hasher.verify(password, user.password_hash):
            raise AuthenticationError("Incorrect email or password")
        assert user.id is not None
        return self._tokens.issue(user.id)


class GetUser:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def execute(self, user_id: int) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user
