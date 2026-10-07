from fastapi import FastAPI

from aceso.shared.api.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(title="Aceso API", version="0.1.0")
    register_error_handlers(app)

    @app.get("/health", tags=["system"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
