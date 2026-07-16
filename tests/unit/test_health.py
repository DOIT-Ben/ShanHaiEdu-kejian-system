from __future__ import annotations

import json
from typing import cast

import httpx

from apps.api.health import DependencyStatus, ReadinessReport, build_readiness_service
from apps.api.logging import JsonFormatter
from apps.api.main import create_app
from apps.api.request_context import REQUEST_ID_HEADER, request_id_context
from apps.api.settings import Settings


class StubReadiness:
    def __init__(self, *, ready: bool) -> None:
        self._ready = ready

    async def check(self) -> ReadinessReport:
        dependency = DependencyStatus(
            name="postgresql",
            ready=self._ready,
            status="available" if self._ready else "unavailable",
        )
        return ReadinessReport(ready=self._ready, dependencies=(dependency,))


async def test_liveness_is_independent_and_preserves_request_id() -> None:
    settings = Settings(_env_file=None, environment="test")
    app = create_app(settings=settings, readiness=StubReadiness(ready=False))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health/live",
            headers={REQUEST_ID_HEADER: "req_test_liveness"},
        )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "req_test_liveness"
    assert response.json()["data"]["status"] == "ok"

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        api_response = await client.get("/api/v2/health/live")
    assert api_response.status_code == 200


async def test_readiness_reports_dependency_failure_without_sensitive_detail() -> None:
    settings = Settings(_env_file=None, environment="test")
    app = create_app(settings=settings, readiness=StubReadiness(ready=False))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    payload = cast(dict[str, object], response.json())
    data = cast(dict[str, object], payload["data"])
    dependencies = cast(list[dict[str, object]], data["dependencies"])
    assert data["status"] == "not_ready"
    assert dependencies == [{"name": "postgresql", "ready": False, "status": "unavailable"}]

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        api_response = await client.get("/api/v2/health/ready")
    assert api_response.status_code == 503


async def test_invalid_request_id_is_replaced() -> None:
    settings = Settings(_env_file=None, environment="test")
    app = create_app(settings=settings, readiness=StubReadiness(ready=True))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health/live",
            headers={REQUEST_ID_HEADER: "invalid id with spaces"},
        )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER].startswith("req_")
    assert response.headers[REQUEST_ID_HEADER] != "invalid id with spaces"


async def test_missing_dependencies_are_reported_independently() -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=None,
        redis_url=None,
        object_storage_health_url=None,
    )

    report = await build_readiness_service(settings).check()

    assert report.ready is False
    assert [dependency.as_dict() for dependency in report.dependencies] == [
        {"name": "postgresql", "ready": False, "status": "not_configured"},
        {"name": "redis", "ready": False, "status": "not_configured"},
        {"name": "object_storage", "ready": False, "status": "not_configured"},
    ]


def test_json_log_has_required_context_without_exception_text() -> None:
    import logging

    formatter = JsonFormatter(service="test-service", environment="test")
    token = request_id_context.set("req_log_test")
    try:
        try:
            raise RuntimeError("secret-value-must-not-appear")
        except RuntimeError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="dependency_failed",
                args=(),
                exc_info=__import__("sys").exc_info(),
            )
        payload = json.loads(formatter.format(record))
    finally:
        request_id_context.reset(token)

    assert payload["service"] == "test-service"
    assert payload["environment"] == "test"
    assert payload["request_id"] == "req_log_test"
    assert payload["exception_type"] == "RuntimeError"
    assert "secret-value-must-not-appear" not in json.dumps(payload)
