from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from aceso.identity.application.use_cases import GetUser
from aceso.identity.domain.entities import User
from aceso.identity.infrastructure.repository import SqlAlchemyUserRepository
from aceso.identity.infrastructure.tokens import JwtAccessTokenIssuer
from aceso.shared.api.deps import SessionDep, SettingsDep
from aceso.shared.domain.errors import AuthenticationError, NotFoundError
from aceso.shared.infrastructure.security import Argon2PasswordHasher, JwtService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_jwt_service(settings: SettingsDep) -> JwtService:
    return JwtService(settings.jwt_secret, settings.jwt_algorithm)


JwtServiceDep = Annotated[JwtService, Depends(get_jwt_service)]


def get_user_repository(session: SessionDep) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


UserRepositoryDep = Annotated[SqlAlchemyUserRepository, Depends(get_user_repository)]


def get_token_issuer(jwt_service: JwtServiceDep, settings: SettingsDep) -> JwtAccessTokenIssuer:
    return JwtAccessTokenIssuer(jwt_service, settings.access_token_expire_minutes)


TokenIssuerDep = Annotated[JwtAccessTokenIssuer, Depends(get_token_issuer)]


def get_password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


PasswordHasherDep = Annotated[Argon2PasswordHasher, Depends(get_password_hasher)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    tokens: TokenIssuerDep,
    users: UserRepositoryDep,
) -> User:
    user_id = tokens.verify(token)
    try:
        return await GetUser(users).execute(user_id)
    except NotFoundError as exc:
        raise AuthenticationError("Could not validate credentials") from exc


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def current_user_id(user: CurrentUserDep) -> int:
    assert user.id is not None
    return user.id


CurrentUserIdDep = Annotated[int, Depends(current_user_id)]
