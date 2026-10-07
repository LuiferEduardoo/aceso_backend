from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from aceso.identity.api.deps import (
    CurrentUserDep,
    PasswordHasherDep,
    TokenIssuerDep,
    UserRepositoryDep,
)
from aceso.identity.api.schemas import Token, UserCreate, UserRead
from aceso.identity.application.use_cases import LoginUser, RegisterUser

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate, users: UserRepositoryDep, hasher: PasswordHasherDep
) -> UserRead:
    user = await RegisterUser(users, hasher).execute(payload.email, payload.password)
    return UserRead.model_validate(user)


@router.post("/login")
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    users: UserRepositoryDep,
    hasher: PasswordHasherDep,
    tokens: TokenIssuerDep,
) -> Token:
    access_token = await LoginUser(users, hasher, tokens).execute(form.username, form.password)
    return Token(access_token=access_token)


@router.get("/me")
async def read_me(user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(user)
