"""FastAPI application factory and process entry point."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.router import router as artifacts_router
from apps.api.assets.project_router import router as project_assets_router
from apps.api.assets.router import router as assets_router
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import register_error_handlers
from apps.api.health import ReadinessProvider, build_readiness_service
from apps.api.identity.authentication import Authenticator
from apps.api.jobs.router import router as jobs_router
from apps.api.lessons.router import router as lessons_router
from apps.api.logging import configure_logging
from apps.api.middleware import RequestContextMiddleware
from apps.api.projects.router import router as projects_router
from apps.api.prompt_runtime.router import router as prompt_runtime_router
from apps.api.settings import Settings, get_settings
from apps.api.uploads.router import router as uploads_router
from apps.api.uploads.storage import ObjectStorage, build_object_storage
from apps.api.workflows.router import router as workflows_router


def create_app(
    settings: Settings | None = None,
    readiness: ReadinessProvider | None = None,
    session_factory: sessionmaker[Session] | None = None,
    object_storage: ObjectStorage | None = None,
    authenticator: Authenticator | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(
        service=resolved_settings.service_name,
        environment=resolved_settings.environment,
        level=resolved_settings.log_level,
    )
    readiness_provider = readiness or build_readiness_service(resolved_settings)
    database_engine = None
    resolved_session_factory = session_factory
    if resolved_session_factory is None and resolved_settings.database_url is not None:
        database_engine = build_engine(resolved_settings.database_url.get_secret_value())
        resolved_session_factory = build_session_factory(database_engine)
    resolved_object_storage = object_storage or build_object_storage(resolved_settings)

    app = FastAPI(
        title="ShanHaiEdu Platform API",
        version="0.1.0",
        docs_url=None if resolved_settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    app.add_middleware(RequestContextMiddleware)
    app.state.settings = resolved_settings
    app.state.readiness = readiness_provider
    app.state.database_engine = database_engine
    app.state.session_factory = resolved_session_factory
    app.state.object_storage = resolved_object_storage
    app.state.authenticator = authenticator
    register_error_handlers(app)
    app.include_router(artifacts_router)
    app.include_router(assets_router)
    app.include_router(project_assets_router)
    app.include_router(projects_router)
    app.include_router(prompt_runtime_router)
    app.include_router(lessons_router)
    app.include_router(uploads_router)
    app.include_router(jobs_router)
    app.include_router(workflows_router)

    @app.get("/health/live", tags=["system"], include_in_schema=False)
    @app.get("/api/v2/health/live", tags=["system"], operation_id="getLiveness")
    async def liveness(request: Request) -> dict[str, object]:
        return {
            "data": {
                "status": "ok",
                "service": resolved_settings.service_name,
                "environment": resolved_settings.environment,
            },
            "request_id": request.state.request_id,
        }

    @app.get("/health/ready", tags=["system"], include_in_schema=False)
    @app.get("/api/v2/health/ready", tags=["system"], operation_id="getReadiness")
    async def readiness_check(request: Request) -> JSONResponse:
        report = await readiness_provider.check()
        return JSONResponse(
            status_code=200 if report.ready else 503,
            content={"data": report.as_dict(), "request_id": request.state.request_id},
        )

    return app


app = create_app()
