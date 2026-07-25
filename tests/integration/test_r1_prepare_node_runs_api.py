from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select

from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.main import create_app
from apps.api.settings import Settings
from apps.api.workflows.artifact_input_selection import ArtifactInputSelectionReader
from apps.api.workflows.models import BranchRun, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import override_test_identity
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_prepare_node_runs_freeze_exact_inputs_and_reject_active_runs(
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
            comment="Approve the exact lesson division for R1 prepare commands.",
            request_id="r1-prepare-approve-division",
        )

    with factory() as session:
        lesson_plan_node = session.scalar(
            select(NodeRun)
            .where(
                NodeRun.node_key == "lesson_plan.generate",
                NodeRun.status == "ready",
            )
            .order_by(NodeRun.id)
            .limit(1)
        )
        assert lesson_plan_node is not None
        branch = lesson_plan_node.branch_run_id
        assert branch is not None
        lesson_unit_id = session.scalar(
            select(BranchRun.lesson_unit_id).where(BranchRun.id == branch)
        )
        assert lesson_unit_id is not None

    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=migrated_database_url,
        ),
        object_storage=FakeObjectStorage(),
    )
    override_test_identity(app, prepared.actor)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            division = await client.post(
                f"/api/v2/projects/{prepared.project_id}/lesson-division/node-runs",
                headers={"Idempotency-Key": "r1-prepare-division-001"},
                json={"material_scope_artifact_version_id": str(prepared.scope_version_id)},
            )
            assert division.status_code == 200, division.text
            division_data = division.json()["data"]
            assert division_data["node_key"] == "lesson.division.generate"
            assert division_data["run_no"] == 2
            assert division_data["status"] == "ready"

            lesson_plan = await client.post(
                f"/api/v2/lessons/{lesson_unit_id}/lesson-plan/node-runs",
                headers={"Idempotency-Key": "r1-prepare-plan-001"},
            )
            assert lesson_plan.status_code == 200, lesson_plan.text
            lesson_plan_data = lesson_plan.json()["data"]
            assert lesson_plan_data["node_key"] == "lesson_plan.generate"
            assert lesson_plan_data["run_no"] == 1
            assert lesson_plan_data["status"] == "ready"

            intro = await client.post(
                f"/api/v2/lessons/{lesson_unit_id}/intro-options/node-runs",
                headers={"Idempotency-Key": "r1-prepare-intro-001"},
                json={"generation_mode": "default_nine"},
            )
            assert intro.status_code == 200, intro.text
            intro_data = intro.json()["data"]
            assert intro_data["node_key"] == "intro.generate_options"
            assert intro_data["run_no"] == 1
            assert intro_data["status"] == "ready"

            replay_cases = (
                (
                    f"/api/v2/projects/{prepared.project_id}/lesson-division/node-runs",
                    "r1-prepare-division-001",
                    {"material_scope_artifact_version_id": str(prepared.scope_version_id)},
                    division_data["id"],
                ),
                (
                    f"/api/v2/lessons/{lesson_unit_id}/lesson-plan/node-runs",
                    "r1-prepare-plan-001",
                    None,
                    lesson_plan_data["id"],
                ),
                (
                    f"/api/v2/lessons/{lesson_unit_id}/intro-options/node-runs",
                    "r1-prepare-intro-001",
                    {"generation_mode": "default_nine"},
                    intro_data["id"],
                ),
            )
            for path, key, payload, expected_id in replay_cases:
                replay = await client.post(
                    path,
                    headers={"Idempotency-Key": key},
                    json=payload,
                )
                assert replay.status_code == 200, replay.text
                assert replay.json()["data"]["id"] == expected_id

            node_ids = {
                "division": UUID(division_data["id"]),
                "lesson_plan": UUID(lesson_plan_data["id"]),
                "intro": UUID(intro_data["id"]),
            }
            with factory() as session:
                selections = {
                    name: ArtifactInputSelectionReader(session, prepared.actor).for_node(node_id)
                    for name, node_id in node_ids.items()
                }
            assert selections == {
                "division": {"approval:material_scope": prepared.scope_version_id},
                "lesson_plan": {"approval:lesson_division": prepared.version_id},
                "intro": {"approval:lesson_division": prepared.version_id},
            }

            with factory() as session, session.begin():
                for node_id in node_ids.values():
                    node = session.get(NodeRun, node_id)
                    assert node is not None
                    node.status = "queued"

            active_cases = (
                (
                    f"/api/v2/projects/{prepared.project_id}/lesson-division/node-runs",
                    "r1-prepare-division-active",
                    {"material_scope_artifact_version_id": str(prepared.scope_version_id)},
                    "LESSON_DIVISION_RUNTIME_INVALID",
                ),
                (
                    f"/api/v2/lessons/{lesson_unit_id}/lesson-plan/node-runs",
                    "r1-prepare-plan-active",
                    None,
                    "LESSON_PLAN_RUNTIME_INVALID",
                ),
                (
                    f"/api/v2/lessons/{lesson_unit_id}/intro-options/node-runs",
                    "r1-prepare-intro-active",
                    {"generation_mode": "default_nine"},
                    "INTRO_OPTION_RUNTIME_INVALID",
                ),
            )
            for path, key, payload, expected_code in active_cases:
                conflict = await client.post(
                    path,
                    headers={"Idempotency-Key": key},
                    json=payload,
                )
                assert conflict.status_code == 409, conflict.text
                assert conflict.json()["error"]["code"] == expected_code

            with factory() as session, session.begin():
                for name in ("lesson_plan", "intro"):
                    node = session.get(NodeRun, node_ids[name])
                    assert node is not None
                    node.status = "failed"

            next_plan = await client.post(
                f"/api/v2/lessons/{lesson_unit_id}/lesson-plan/node-runs",
                headers={"Idempotency-Key": "r1-prepare-plan-002"},
            )
            assert next_plan.status_code == 200, next_plan.text
            assert next_plan.json()["data"]["run_no"] == 2

            next_intro = await client.post(
                f"/api/v2/lessons/{lesson_unit_id}/intro-options/node-runs",
                headers={"Idempotency-Key": "r1-prepare-intro-002"},
                json={"generation_mode": "default_nine"},
            )
            assert next_intro.status_code == 200, next_intro.text
            assert next_intro.json()["data"]["run_no"] == 2
    finally:
        app.state.database_engine.dispose()
        engine.dispose()
