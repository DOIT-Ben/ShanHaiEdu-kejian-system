"""FastAPI application factory and process entry point."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from apps.api.health import ReadinessProvider, build_readiness_service
from apps.api.logging import configure_logging
from apps.api.middleware import RequestContextMiddleware
from apps.api.settings import Settings, get_settings


def create_app(
    settings: Settings | None = None,
    readiness: ReadinessProvider | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(
        service=resolved_settings.service_name,
        environment=resolved_settings.environment,
        level=resolved_settings.log_level,
    )
    readiness_provider = readiness or build_readiness_service(resolved_settings)

    app = FastAPI(
        title="ShanHaiEdu Platform API",
        version="0.1.0",
        docs_url=None if resolved_settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    app.add_middleware(RequestContextMiddleware)
    app.state.settings = resolved_settings
    app.state.readiness = readiness_provider

    @app.get("/health/live", tags=["system"])
    async def liveness(request: Request) -> dict[str, object]:
        return {
            "data": {
                "status": "ok",
                "service": resolved_settings.service_name,
                "environment": resolved_settings.environment,
            },
            "request_id": request.state.request_id,
        }

    @app.get("/health/ready", tags=["system"])
    async def readiness_check(request: Request) -> JSONResponse:
        report = await readiness_provider.check()
        return JSONResponse(
            status_code=200 if report.ready else 503,
            content={"data": report.as_dict(), "request_id": request.state.request_id},
        )

    return app


app = create_app()
