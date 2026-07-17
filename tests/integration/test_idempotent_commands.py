from __future__ import annotations

import httpx
from sqlalchemy import func, select

from apps.api.database import build_engine, build_session_factory
from apps.api.main import create_app
from apps.api.projects.models import Project
from apps.api.settings import Settings
from tests.conftest import run_migration
from tests.fakes.identity import configure_test_identity


async def test_project_command_replays_and_conflicts_by_request_digest(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    settings = Settings(_env_file=None, environment="test", database_url=postgres_database_url)
    app = create_app(settings=settings)
    configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    payload = {"title": "Fractions", "knowledge_point": "One half"}
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "project-create-001"},
                json=payload,
            )
            replay = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "project-create-001"},
                json=payload,
            )
            conflict = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "project-create-001"},
                json={**payload, "title": "Different title"},
            )
        assert first.status_code == 201
        assert replay.status_code == 201
        assert replay.json()["data"] == first.json()["data"]
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

        factory = build_session_factory(build_engine(postgres_database_url))
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Project)) == 1
    finally:
        app.state.database_engine.dispose()
