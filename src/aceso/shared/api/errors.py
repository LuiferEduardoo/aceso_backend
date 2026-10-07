from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from aceso.shared.domain.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    IntegrationError,
    InvalidOperationError,
    NotFoundError,
)

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    InvalidOperationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    IntegrationError: status.HTTP_502_BAD_GATEWAY,
}


async def _domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    code = next(
        (code for cls, code in _STATUS_BY_ERROR.items() if isinstance(exc, cls)),
        status.HTTP_400_BAD_REQUEST,
    )
    headers = {"WWW-Authenticate": "Bearer"} if code == status.HTTP_401_UNAUTHORIZED else None
    return JSONResponse(status_code=code, content={"detail": exc.message}, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
