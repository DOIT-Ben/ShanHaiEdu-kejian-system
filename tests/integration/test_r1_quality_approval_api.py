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

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import ActorContext
from apps.api.lessons.models import LessonUnit
from apps.api.lessons.runtime_service import LessonDivisionRuntimeService
from apps.api.main import create_app
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.settings import Settings
from apps.api.workflows.models import NodeInputSnapshot, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import override_test_identity, seed_test_actor
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_intro_option_runtime import (
    _generate_default_nine,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from tests.integration.test_lesson_division_runtime import (
    _seed_material_and_scope,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from tests.integration.test_lesson_plan_runtime import (
    _prepare_generated_lesson_plan,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from workers.artifact_quality import execute_artifact_quality_node

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"
ApprovalArtifactKind = Literal["lesson_division", "lesson_plan", "intro_option_set"]


@dataclass(frozen=True, slots=True)
class ApprovalTarget:
    actor: ActorContext
    project_id: UUID
    lesson_unit_id: UUID | None
    version_id: UUID
    gate_node_key: str


@pytest.mark.parametrize(
    ("artifact_kind", "gate_node_key"),
    [
        ("lesson_division", "lesson.division.approve"),
        ("lesson_plan", "lesson_plan.approve"),
        ("intro_option_set", "intro.approve"),
    ],
)
async def test_review_api_opens_exact_quality_gate_before_approval(
    migrated_database_url: str,
    artifact_kind: ApprovalArtifactKind,
    gate_node_key: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    target = await _prepare_approval_target(factory, artifact_kind, gate_node_key)
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
            premature = await client.post(
                f"/api/v2/artifact-versions/{target.version_id}/approvals",
                headers={"Idempotency-Key": f"r1-approve-{artifact_kind}-premature"},
                json={"action": "approve", "comment": "No quality evidence yet."},
            )
            assert premature.status_code == 409, premature.text
            assert premature.json()["error"]["code"] == "ARTIFACT_QUALITY_REQUIRED"

            accepted = await client.post(
                f"/api/v2/artifact-versions/{target.version_id}/quality-validations",
                headers={"Idempotency-Key": f"r1-approve-{artifact_kind}-quality"},
            )
            assert accepted.status_code == 202, accepted.text
            validate_node_id = UUID(accepted.json()["data"]["node_run_id"])

            quality = execute_artifact_quality_node(
                migrated_database_url,
                validate_node_id,
                runtime_quality_validator_registry(),
            )
            assert quality is not None
            assert quality.conclusion == "passed"

            approved = await client.post(
                f"/api/v2/artifact-versions/{target.version_id}/approvals",
                headers={"Idempotency-Key": f"r1-approve-{artifact_kind}-final"},
                json={"action": "approve", "comment": "Approve exact passed evidence."},
            )
            assert approved.status_code == 201, approved.text
            approved_data = approved.json()["data"]
            approval_id = UUID(approved_data["id"])

            replay = await client.post(
                f"/api/v2/artifact-versions/{target.version_id}/approvals",
                headers={"Idempotency-Key": f"r1-approve-{artifact_kind}-final"},
                json={"action": "approve", "comment": "Approve exact passed evidence."},
            )
            assert replay.status_code == 201, replay.text
            assert replay.json()["data"] == approved_data

        with factory() as session:
            artifact = session.scalar(
                select(Artifact)
                .join(ArtifactVersion, ArtifactVersion.artifact_id == Artifact.id)
                .where(ArtifactVersion.id == target.version_id)
            )
            approval = session.get(Approval, approval_id)
            version = session.get(ArtifactVersion, target.version_id)
            report = session.get(ArtifactQualityReport, quality.report_id)
            validate = session.get(NodeRun, validate_node_id)
            gate = session.scalar(
                select(NodeRun).where(
                    NodeRun.organization_id == target.actor.organization_id,
                    NodeRun.node_key == target.gate_node_key,
                    NodeRun.status == "approved",
                )
            )
            assert artifact is not None
            assert approval is not None
            assert version is not None
            assert report is not None
            assert validate is not None
            assert gate is not None
            assert artifact.status == "approved"
            assert artifact.current_submitted_version_id is None
            assert artifact.current_approved_version_id == target.version_id
            assert report.project_id == target.project_id
            assert report.lesson_unit_id == target.lesson_unit_id
            assert report.source_artifact_version_id == target.version_id
            assert report.validate_node_run_id == validate_node_id
            assert validate.status == "approved"
            assert approval.artifact_version_id == target.version_id
            assert approval.action == "approve"
            assert approval.quality_evidence_json["report_id"] == str(report.id)
            assert approval.quality_evidence_json["evidence_hash"] == report.evidence_hash
            if target.lesson_unit_id is None:
                lesson_count = session.scalar(
                    select(func.count())
                    .select_from(LessonUnit)
                    .where(
                        LessonUnit.project_id == target.project_id,
                        LessonUnit.status == "active",
                    )
                )
                assert lesson_count == len(version.content_json["lesson_units"])
            else:
                assert (
                    session.scalar(
                        select(func.count())
                        .select_from(NodeInputSnapshot)
                        .where(
                            NodeInputSnapshot.node_run_id == gate.id,
                            NodeInputSnapshot.source_version_id.in_((target.version_id, report.id)),
                        )
                    )
                    == 2
                )
    finally:
        app.state.database_engine.dispose()
        engine.dispose()


async def _prepare_approval_target(
    factory: sessionmaker[Session],
    artifact_kind: ApprovalArtifactKind,
    gate_node_key: str,
) -> ApprovalTarget:
    if artifact_kind == "lesson_division":
        return await _prepare_unvalidated_division(factory, gate_node_key)
    if artifact_kind == "lesson_plan":
        prepared = await _prepare_generated_lesson_plan(factory)
    else:
        prepared = await _generate_default_nine(factory)
    with factory() as session:
        version = session.get(ArtifactVersion, prepared.version_id)
        assert version is not None
        artifact = session.get(Artifact, version.artifact_id)
        assert artifact is not None
        return ApprovalTarget(
            actor=prepared.actor,
            project_id=artifact.project_id,
            lesson_unit_id=artifact.lesson_unit_id,
            version_id=version.id,
            gate_node_key=gate_node_key,
        )


async def _prepare_unvalidated_division(
    factory: sessionmaker[Session],
    gate_node_key: str,
) -> ApprovalTarget:
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        published = ContentReleasePublisher(session).publish(
            load_builtin_courseware_release(ROOT),
            published_by=actor.principal_id,
        )
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="R1 quality approval", knowledge_point="1-5")
        )
        definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.content_package_version_id
                == published.content_package_version_id,
                ContentDefinitionVersion.definition_key == "lesson.division.generate.output",
            )
        )
        assert definition is not None
        _seed_material_and_scope(
            session,
            actor,
            project.id,
            definition.id,
            case,
            approved_evidence_keys=None,
        )
        nodes = LessonDivisionRuntimeService(session, actor).initialize(project.id)
    committed = await NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, actor),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(output)
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    ).execute(nodes.generate_node_run_id, request_id="r1-quality-approval-division")
    return ApprovalTarget(
        actor=actor,
        project_id=project.id,
        lesson_unit_id=None,
        version_id=committed.artifact_version_id,
        gate_node_key=gate_node_key,
    )
