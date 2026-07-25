from __future__ import annotations

import json
from pathlib import Path

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select

from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.lessons.models import LessonUnit
from apps.api.main import create_app
from apps.api.settings import Settings
from apps.api.workflows.models import BranchRun, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import override_test_identity
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_intro_option_prepare_is_idempotent_and_exactly_lesson_scoped(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    outputs = build_golden_branch_source_outputs(case)
    prepared = await _prepare_approval(factory, case, outputs["lesson.division.generate"])
    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="approve",
            comment="Approve the exact division used by the Intro rescue test.",
            request_id="r1-intro-approve-division",
        )
    with factory() as session:
        lesson_unit_id = session.scalar(
            select(LessonUnit.id).where(
                LessonUnit.project_id == prepared.project_id,
                LessonUnit.status == "active",
            )
        )
        assert lesson_unit_id is not None

    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=SecretStr(migrated_database_url),
        session_access_code=None,
        session_allowed_origins=[],
        session_csrf_secret=None,
        session_teacher_principal_id=None,
    )
    app = create_app(settings=settings, object_storage=FakeObjectStorage())
    override_test_identity(app, prepared.actor)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "generation_mode": "default_nine",
                "source_artifact_version_id": None,
            }
            headers = {"Idempotency-Key": "r1-intro-prepare-default-nine"}
            created = await client.post(
                f"/api/v2/lessons/{lesson_unit_id}/intro-options/node-runs",
                headers=headers,
                json=payload,
            )
            replayed = await client.post(
                f"/api/v2/lessons/{lesson_unit_id}/intro-options/node-runs",
                headers=headers,
                json=payload,
            )
    finally:
        app.state.database_engine.dispose()
        engine.dispose()

    assert created.status_code == 200, created.text
    assert replayed.status_code == 200, replayed.text
    node_id = created.json()["data"]["id"]
    assert replayed.json()["data"]["id"] == node_id
    with factory() as session:
        node = session.get(NodeRun, node_id)
        assert node is not None and node.branch_run_id is not None
        branch = session.get(BranchRun, node.branch_run_id)
        assert branch is not None
        assert node.node_key == "intro.generate_options"
        assert branch.project_id == prepared.project_id
        assert branch.lesson_unit_id == lesson_unit_id
        assert (
            session.scalar(
                select(func.count())
                .select_from(NodeRun)
                .where(
                    NodeRun.branch_run_id == branch.id,
                    NodeRun.node_key == "intro.generate_options",
                    NodeRun.status == "ready",
                )
            )
            == 1
        )
