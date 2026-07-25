from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonUnit
from apps.api.main import create_app
from apps.api.settings import Settings
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import override_test_identity, seed_test_actor
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_intro_option_runtime import (
    _generate_default_nine,  # pyright: ignore[reportPrivateUsage]
)
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from workers.artifact_quality import execute_artifact_quality_node

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
        workflow = session.get(WorkflowRun, branch.workflow_run_id)
        assert workflow is not None
        assert node.node_key == "intro.generate_options"
        assert workflow.project_id == prepared.project_id
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


async def test_intro_options_restore_edit_quality_exact_approval_and_selection(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    prepared = await _generate_default_nine(factory)
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
            initial = await _get_intro_artifact(
                client,
                prepared.project_id,
                prepared.lesson_unit_id,
            )
            artifact = cast(dict[str, Any], initial["artifact"])
            draft = cast(dict[str, Any], artifact["current_draft"])
            assert artifact["id"] == str(prepared.artifact_id)
            assert draft["based_on_version_id"] == str(prepared.version_id)

            edited = deepcopy(cast(dict[str, Any], draft["content"]))
            options = cast(list[dict[str, Any]], edited["options"])
            options[0]["title"] = "教师编辑后的科普课堂导入"
            saved = await client.put(
                f"/api/v2/artifacts/{prepared.artifact_id}/drafts/main",
                headers={
                    "Idempotency-Key": "r1-intro-save-edited-options",
                    "If-Match": f'W/"{draft["lock_version"]}"',
                },
                json={"content": edited},
            )
            assert saved.status_code == 200, saved.text
            saved_draft = saved.json()["data"]

            submitted = await client.post(
                f"/api/v2/artifacts/{prepared.artifact_id}/versions",
                headers={
                    "Idempotency-Key": "r1-intro-submit-edited-options",
                    "If-Match": f'W/"{saved_draft["lock_version"]}"',
                },
                json={"draft_branch": "main"},
            )
            assert submitted.status_code == 201, submitted.text
            submitted_version_id = UUID(submitted.json()["data"]["id"])
            assert submitted_version_id != prepared.version_id

            quality = await client.post(
                "/api/v2/lessons/"
                f"{prepared.lesson_unit_id}/intro-options/artifact-versions/"
                f"{submitted_version_id}/quality-validations",
                headers={"Idempotency-Key": "r1-intro-quality-edited-options"},
            )
            assert quality.status_code == 202, quality.text
            quality_node_id = UUID(quality.json()["data"]["node_run_id"])
            report = execute_artifact_quality_node(
                migrated_database_url,
                quality_node_id,
                runtime_quality_validator_registry(),
            )
            assert report is not None and report.conclusion == "passed"

            wrong_version = await client.post(
                f"/api/v2/artifact-versions/{prepared.version_id}/approvals",
                headers={"Idempotency-Key": "r1-intro-reject-old-version"},
                json={"action": "approve", "comment": "Must not approve the old version."},
            )
            assert wrong_version.status_code == 409, wrong_version.text

            approved = await client.post(
                f"/api/v2/artifact-versions/{submitted_version_id}/approvals",
                headers={"Idempotency-Key": "r1-intro-approve-exact-version"},
                json={"action": "approve", "comment": "Approve the exact edited options."},
            )
            assert approved.status_code == 201, approved.text

            selected = await client.post(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-selections",
                headers={"Idempotency-Key": "r1-intro-select-approved-option"},
                json={
                    "artifact_version_id": str(submitted_version_id),
                    "option_key": options[0]["option_key"],
                },
            )
            assert selected.status_code == 201, selected.text
            assert selected.json()["data"]["artifact_version_id"] == str(submitted_version_id)

            restored = await _get_intro_artifact(
                client,
                prepared.project_id,
                prepared.lesson_unit_id,
            )
            restored_options = await client.get(
                f"/api/v2/lessons/{prepared.lesson_unit_id}/intro-options"
            )
            assert restored_options.status_code == 200, restored_options.text
            restored_artifact = cast(dict[str, Any], restored["artifact"])
            restored_version = cast(
                dict[str, Any],
                restored_artifact["current_approved_version"],
            )
            restored_report = cast(dict[str, Any], restored["quality_report"])
            restored_approval = cast(dict[str, Any], restored["latest_approval"])
            restored_selection = cast(
                dict[str, Any],
                restored_options.json()["data"]["current_selection"],
            )
            assert restored_version["id"] == str(submitted_version_id)
            assert restored_version["content"] == edited
            assert restored_report["artifact_version_id"] == str(submitted_version_id)
            assert restored_report["conclusion"] == "passed"
            assert restored_approval["artifact_version_id"] == str(submitted_version_id)
            assert restored_approval["action"] == "approve"
            assert restored_selection["artifact_version_id"] == str(submitted_version_id)
            assert restored_selection["option_key"] == options[0]["option_key"]
            assert restored_selection["snapshot"]["title"] == options[0]["title"]

            foreign_actor = _seed_foreign_actor(factory)
            override_test_identity(app, foreign_actor)
            cross_tenant = await client.get(
                f"/api/v2/projects/{prepared.project_id}/lessons/"
                f"{prepared.lesson_unit_id}/intro-options/artifact"
            )
            assert cross_tenant.status_code == 404, cross_tenant.text
    finally:
        app.state.database_engine.dispose()
        engine.dispose()


async def _get_intro_artifact(
    client: httpx.AsyncClient,
    project_id: UUID,
    lesson_unit_id: UUID,
) -> dict[str, Any]:
    response = await client.get(
        f"/api/v2/projects/{project_id}/lessons/{lesson_unit_id}/intro-options/artifact"
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json()["data"])


def _seed_foreign_actor(factory: sessionmaker[Session]):
    organization_id = new_uuid7()
    with factory() as session, session.begin():
        session.add(
            Organization(
                id=organization_id,
                slug=f"r1-intro-{organization_id.hex[:12]}",
                name="R1 Intro foreign tenant",
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        return seed_test_actor(
            session,
            organization_id=organization_id,
            user_id=new_uuid7(),
            principal_id=new_uuid7(),
            member_id=new_uuid7(),
            email=f"r1-intro-{organization_id.hex[:12]}@example.test",
            display_name="R1 Intro foreign teacher",
        )
