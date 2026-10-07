import pytest

from aceso.identity.application.use_cases import GetUser, LoginUser, RegisterUser
from aceso.identity.domain.entities import User
from aceso.shared.domain.errors import AuthenticationError, ConflictError, NotFoundError


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}

    async def get_by_id(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def add(self, user: User) -> User:
        user.id = len(self.users) + 1
        self.users[user.id] = user
        return user


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


class FakeTokens:
    def issue(self, user_id: int) -> str:
        return f"token-{user_id}"


async def test_register_normalizes_email_and_hashes_password() -> None:
    users = FakeUserRepository()
    user = await RegisterUser(users, FakeHasher()).execute("  Runner@Example.COM ", "password1")
    assert user.email == "runner@example.com"
    assert user.password_hash == "hashed:password1"


async def test_register_rejects_duplicate_email() -> None:
    users = FakeUserRepository()
    await RegisterUser(users, FakeHasher()).execute("a@example.com", "password1")
    with pytest.raises(ConflictError):
        await RegisterUser(users, FakeHasher()).execute("A@example.com", "password2")


async def test_login_returns_token_for_valid_credentials() -> None:
    users = FakeUserRepository()
    await RegisterUser(users, FakeHasher()).execute("a@example.com", "password1")
    token = await LoginUser(users, FakeHasher(), FakeTokens()).execute("A@example.com", "password1")
    assert token == "token-1"


@pytest.mark.parametrize(("email", "password"), [("a@example.com", "bad"), ("x@example.com", "p")])
async def test_login_rejects_invalid_credentials(email: str, password: str) -> None:
    users = FakeUserRepository()
    await RegisterUser(users, FakeHasher()).execute("a@example.com", "password1")
    with pytest.raises(AuthenticationError):
        await LoginUser(users, FakeHasher(), FakeTokens()).execute(email, password)


async def test_get_user_raises_when_missing() -> None:
    with pytest.raises(NotFoundError):
        await GetUser(FakeUserRepository()).execute(99)
