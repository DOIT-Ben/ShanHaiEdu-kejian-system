from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.main import create_app
from apps.api.reliability.models import OutboxEvent
from apps.api.settings import Settings
from apps.api.workflows.models import BranchRun, NodeInputSnapshot, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import override_test_identity, seed_test_actor
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_intro_option_runtime import (
    _generate_default_nine,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from tests.integration.test_lesson_plan_runtime import (
    _prepare_generated_lesson_plan,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
QualityArtifactKind = Literal["lesson_division", "lesson_plan", "intro_option_set"]


@dataclass(frozen=True, slots=True)
class QualityTarget:
    actor: ActorContext
    project_id: UUID
    lesson_unit_id: UUID | None
    version_id: UUID
    validate_node_key: str


@pytest.mark.parametrize(
    ("artifact_kind", "expected_validate_node_key"),
    [
        ("lesson_division", "lesson.division.validate"),
        ("lesson_plan", "lesson_plan.validate"),
        ("intro_option_set", "intro.validate"),
    ],
)
async def test_quality_validation_api_queues_exact_node_and_replays(
    migrated_database_url: str,
    artifact_kind: QualityArtifactKind,
    expected_validate_node_key: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    target = await _prepare_quality_target(factory, artifact_kind, expected_validate_node_key)
    outsider = _seed_outsider(factory, target.actor.organization_id)

    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=migrated_database_url,
        ),
        object_storage=FakeObjectStorage(),
    )
    override_test_identity(app, target.actor)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            accepted = await client.post(
                f"/api/v2/artifact-versions/{target.version_id}/quality-validations",
                headers={"Idempotency-Key": f"r1-quality-{artifact_kind}-001"},
            )
            assert accepted.status_code == 202, accepted.text
            accepted_data = accepted.json()["data"]
            validate_node_id = UUID(accepted_data["node_run_id"])
            assert accepted_data == {
                "node_run_id": str(validate_node_id),
                "status": accepted_data["status"],
                "events_url": f"/api/v2/projects/{target.project_id}/events/stream",
            }

            replay = await client.post(
                f"/api/v2/artifact-versions/{target.version_id}/quality-validations",
                headers={"Idempotency-Key": f"r1-quality-{artifact_kind}-001"},
            )
            assert replay.status_code == 202, replay.text
            assert replay.json()["data"] == accepted_data

            missing = await client.post(
                f"/api/v2/artifact-versions/{new_uuid7()}/quality-validations",
                headers={"Idempotency-Key": f"r1-quality-{artifact_kind}-missing"},
            )
            assert missing.status_code == 404, missing.text
            assert missing.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"

            material_scope_version_id = _material_scope_version_id(factory, target.project_id)
            unsupported = await client.post(
                f"/api/v2/artifact-versions/{material_scope_version_id}/quality-validations",
                headers={"Idempotency-Key": f"r1-quality-{artifact_kind}-scope"},
            )
            assert unsupported.status_code == 409, unsupported.text
            assert unsupported.json()["error"]["code"] == "ARTIFACT_QUALITY_UNSUPPORTED"

            override_test_identity(app, outsider)
            invisible = await client.post(
                f"/api/v2/artifact-versions/{target.version_id}/quality-validations",
                headers={"Idempotency-Key": f"r1-quality-{artifact_kind}-outsider"},
            )
            assert invisible.status_code == 404, invisible.text
            assert invisible.json()["error"]["code"] == "ARTIFACT_NOT_FOUND"

        with factory() as session:
            node = session.get(NodeRun, validate_node_id)
            assert node is not None
            assert node.node_key == target.validate_node_key
            assert node.status == accepted_data["status"]
            if target.lesson_unit_id is None:
                assert node.branch_run_id is None
            else:
                assert node.branch_run_id is not None
                assert (
                    session.scalar(
                        select(BranchRun.lesson_unit_id).where(BranchRun.id == node.branch_run_id)
                    )
                    == target.lesson_unit_id
                )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(NodeInputSnapshot)
                    .where(
                        NodeInputSnapshot.node_run_id == validate_node_id,
                        NodeInputSnapshot.source_version_id == target.version_id,
                    )
                )
                == 1
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(
                        OutboxEvent.topic == "artifact.quality_validation.queued",
                        OutboxEvent.aggregate_type == "node_run",
                        OutboxEvent.aggregate_id == validate_node_id,
                    )
                )
                == 1
            )
    finally:
        app.state.database_engine.dispose()
        engine.dispose()


async def _prepare_quality_target(
    factory: sessionmaker[Session],
    artifact_kind: QualityArtifactKind,
    expected_validate_node_key: str,
) -> QualityTarget:
    if artifact_kind == "lesson_division":
        case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
        outputs = build_golden_branch_source_outputs(case)
        prepared = await _prepare_approval(factory, case, outputs["lesson.division.generate"])
        return QualityTarget(
            actor=prepared.actor,
            project_id=prepared.project_id,
            lesson_unit_id=None,
            version_id=prepared.version_id,
            validate_node_key=expected_validate_node_key,
        )
    if artifact_kind == "lesson_plan":
        prepared = await _prepare_generated_lesson_plan(factory)
    else:
        prepared = await _generate_default_nine(factory)
    with factory() as session:
        version = session.get(ArtifactVersion, prepared.version_id)
        assert version is not None
        artifact = session.get(Artifact, version.artifact_id)
        assert artifact is not None
        return QualityTarget(
            actor=prepared.actor,
            project_id=artifact.project_id,
            lesson_unit_id=artifact.lesson_unit_id,
            version_id=version.id,
            validate_node_key=expected_validate_node_key,
        )


def _material_scope_version_id(
    factory: sessionmaker[Session],
    project_id: UUID,
) -> UUID:
    with factory() as session:
        version_id = session.scalar(
            select(Artifact.current_approved_version_id).where(
                Artifact.project_id == project_id,
                Artifact.artifact_type == "material_scope",
                Artifact.deleted_at.is_(None),
            )
        )
        assert version_id is not None
        return version_id


def _seed_outsider(
    factory: sessionmaker[Session],
    organization_id: UUID,
) -> ActorContext:
    with factory() as session, session.begin():
        return seed_test_actor(
            session,
            organization_id=organization_id,
            user_id=new_uuid7(),
            principal_id=new_uuid7(),
            member_id=new_uuid7(),
            email=f"quality-outsider-{new_uuid7()}@example.test",
            display_name="Quality Outsider",
        )
