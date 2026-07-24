"""FastAPI application factory and process entry point."""

from __future__ import annotations

from typing import Any, cast

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.cors import CORSMiddleware

from apps.api.artifacts.router import router as artifacts_router
from apps.api.assets.project_router import router as project_assets_router
from apps.api.assets.router import router as assets_router
from apps.api.creation.router import router as creation_router
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import register_error_handlers
from apps.api.health import ReadinessProvider, build_readiness_service
from apps.api.identity.authentication import Authenticator
from apps.api.identity.dependencies import enforce_session_request_security
from apps.api.identity.session_router import router as session_router
from apps.api.identity.session_service import DatabaseSessionService
from apps.api.intro_options.router import router as intro_options_router
from apps.api.jobs.router import router as jobs_router
from apps.api.lessons.router import router as lessons_router
from apps.api.logging import configure_logging
from apps.api.middleware import RequestContextMiddleware, SessionLoginBodyLimitMiddleware
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
    session_service = None
    if resolved_session_factory is not None and resolved_settings.session_access_code is not None:
        session_service = DatabaseSessionService(resolved_session_factory, resolved_settings)
    resolved_object_storage = object_storage or build_object_storage(resolved_settings)
    app = _build_api_app(resolved_settings)
    app.state.settings = resolved_settings
    app.state.readiness = readiness_provider
    app.state.database_engine = database_engine
    app.state.session_factory = resolved_session_factory
    app.state.object_storage = resolved_object_storage
    app.state.session_service = session_service
    app.state.authenticator = authenticator or session_service
    register_error_handlers(app)
    app.include_router(session_router)
    app.include_router(artifacts_router)
    app.include_router(creation_router)
    app.include_router(assets_router)
    app.include_router(project_assets_router)
    app.include_router(projects_router)
    app.include_router(prompt_runtime_router)
    app.include_router(lessons_router)
    app.include_router(intro_options_router)
    app.include_router(uploads_router)
    app.include_router(jobs_router)
    app.include_router(workflows_router)
    _include_health_routes(app, resolved_settings, readiness_provider)
    _configure_openapi_security_contract(app)
    return app


def _build_api_app(settings: Settings) -> FastAPI:
    app = FastAPI(
        title="ShanHaiEdu Platform API",
        version="0.1.0",
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        dependencies=[Depends(enforce_session_request_security)],
    )
    app.add_middleware(SessionLoginBodyLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    if settings.session_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.session_allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=[
                "Accept",
                "Content-Type",
                "Idempotency-Key",
                "If-Match",
                "Last-Event-ID",
                "X-CSRF-Token",
            ],
            expose_headers=["ETag", "X-Request-ID"],
        )
    return app


def _include_health_routes(
    app: FastAPI,
    settings: Settings,
    readiness: ReadinessProvider,
) -> None:

    @app.get("/health/live", tags=["system"], include_in_schema=False)
    @app.get("/api/v2/health/live", tags=["system"], operation_id="getLiveness")
    async def liveness(request: Request) -> dict[str, object]:
        return {
            "data": {
                "status": "ok",
                "service": settings.service_name,
                "environment": settings.environment,
            },
            "request_id": request.state.request_id,
        }

    @app.get("/health/ready", tags=["system"], include_in_schema=False)
    @app.get("/api/v2/health/ready", tags=["system"], operation_id="getReadiness")
    async def readiness_check(request: Request) -> JSONResponse:
        report = await readiness.check()
        return JSONResponse(
            status_code=200 if report.ready else 503,
            content={"data": report.as_dict(), "request_id": request.state.request_id},
        )


def _configure_openapi_security_contract(app: FastAPI) -> None:
    generated_openapi = app.openapi

    def openapi_with_session_security() -> dict[str, Any]:
        schema = generated_openapi()
        components = cast(dict[str, Any], schema.setdefault("components", {}))
        security_schemes = cast(dict[str, Any], components.setdefault("securitySchemes", {}))
        security_schemes["BrowserOrigin"] = {
            "type": "apiKey",
            "in": "header",
            "name": "Origin",
            "description": (
                "Browser-controlled request origin. User agents attach this header; "
                "application callers must not synthesize it from user input."
            ),
        }
        security_schemes["CsrfToken"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-CSRF-Token",
            "description": (
                "Server-issued token bound to the current session and injected by the web client."
            ),
        }
        schema["security"] = [{"cookieAuth": []}]
        paths = cast(dict[str, dict[str, Any]], schema.get("paths", {}))
        for path_item in paths.values():
            for method, operation_value in path_item.items():
                if not isinstance(operation_value, dict):
                    continue
                operation = cast(dict[str, Any], operation_value)
                operation_id = operation.get("operationId")
                if operation_id in {"getLiveness", "getReadiness"}:
                    operation["security"] = []
                elif operation_id == "createSession":
                    operation["security"] = [{"BrowserOrigin": []}]
                elif method in {"post", "put", "patch", "delete"}:
                    operation["security"] = [
                        {"BrowserOrigin": [], "CsrfToken": [], "cookieAuth": []}
                    ]
                elif method in {"get", "head", "options"}:
                    operation["security"] = [{"cookieAuth": []}]
        return schema

    app.openapi = openapi_with_session_security


app = create_app()
