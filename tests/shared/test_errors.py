import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from aceso.shared.api.errors import register_error_handlers
from aceso.shared.domain.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    IntegrationError,
    InvalidOperationError,
    NotFoundError,
)


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (NotFoundError("missing"), 404),
        (ConflictError("dup"), 409),
        (InvalidOperationError("bad"), 422),
        (AuthenticationError("nope"), 401),
        (IntegrationError("down"), 502),
        (DomainError("generic"), 400),
    ],
)
async def test_domain_errors_map_to_http_status(error: DomainError, status_code: int) -> None:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise error

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == status_code
    assert response.json() == {"detail": error.message}
