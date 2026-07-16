#!/usr/bin/env python3
"""Verify that local dependencies, API health, and worker bootstrap are usable."""

from __future__ import annotations

import asyncio
from typing import cast

import httpx

from apps.api.health import build_readiness_service
from apps.api.main import create_app
from apps.api.request_context import REQUEST_ID_HEADER
from apps.api.settings import Settings


async def run_smoke() -> None:
    settings = Settings()
    readiness = build_readiness_service(settings)
    report = await readiness.check()
    if not report.ready:
        failed = ", ".join(
            dependency.name for dependency in report.dependencies if not dependency.ready
        )
        raise SystemExit(f"local dependencies are not ready: {failed}")

    transport = httpx.ASGITransport(app=create_app(settings=settings, readiness=readiness))
    async with httpx.AsyncClient(transport=transport, base_url="http://local.test") as client:
        request_id = "req_local_stack_smoke"
        live_response = await client.get(
            "/health/live",
            headers={REQUEST_ID_HEADER: request_id},
        )
        live_response.raise_for_status()
        if live_response.headers.get(REQUEST_ID_HEADER) != request_id:
            raise AssertionError("liveness response did not preserve request ID")

        ready_response = await client.get("/health/ready")
        ready_response.raise_for_status()
        payload = cast(dict[str, object], ready_response.json())
        data = cast(dict[str, object], payload["data"])
        if data.get("status") != "ready":
            raise AssertionError(payload)


def main() -> int:
    asyncio.run(run_smoke())
    print("local backend stack smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
