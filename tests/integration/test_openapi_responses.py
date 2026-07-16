from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from apps.api.health import DependencyStatus, ReadinessReport
from apps.api.main import create_app
from apps.api.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


class StubReadiness:
    def __init__(self, *, ready: bool) -> None:
        self._ready = ready

    async def check(self) -> ReadinessReport:
        status = DependencyStatus(
            name="postgresql",
            ready=self._ready,
            status="available" if self._ready else "unavailable",
        )
        return ReadinessReport(ready=self._ready, dependencies=(status,))


def load_openapi() -> dict[str, Any]:
    document = yaml.safe_load(
        (ROOT / "contracts/api-surface.openapi.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(document, dict)
    return document


def response_schema(path: str, status: str) -> dict[str, Any]:
    openapi = load_openapi()
    schema = deepcopy(
        openapi["paths"][path]["get"]["responses"][status]["content"]["application/json"]["schema"]
    )
    schema["components"] = deepcopy(openapi["components"])
    return schema


async def assert_response_matches_contract(*, ready: bool, path: str, status: str) -> None:
    settings = Settings(_env_file=None, environment="test")
    app = create_app(settings=settings, readiness=StubReadiness(ready=ready))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/api/v2{path}")

    assert response.status_code == int(status)
    Draft202012Validator(
        response_schema(path, status),
        format_checker=FormatChecker(),
    ).validate(response.json())


async def test_liveness_response_matches_openapi() -> None:
    await assert_response_matches_contract(ready=False, path="/health/live", status="200")


async def test_ready_response_matches_openapi() -> None:
    await assert_response_matches_contract(ready=True, path="/health/ready", status="200")


async def test_not_ready_response_matches_openapi() -> None:
    await assert_response_matches_contract(ready=False, path="/health/ready", status="503")
