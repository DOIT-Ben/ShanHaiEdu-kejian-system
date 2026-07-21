from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifact_quality.service import ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import SqlAlchemyArtifactQualityTransactionFactory
from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.assets.models import FileAsset, FileAssetVersion, MaterialParseVersion
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonBranchConfig, LessonUnit
from apps.api.lessons.runtime_service import LessonDivisionRuntimeService
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry
from apps.api.uploads.models import SourceMaterial
from apps.api.workflows.models import BranchRun, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import seed_test_actor

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_generated_validated_approved_division_atomically_materializes_lesson_runtime(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        published = ContentReleasePublisher(session).publish(
            load_builtin_courseware_release(ROOT),
            published_by=actor.principal_id,
        )
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Lesson division runtime", knowledge_point="1-5")
        )
        definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.content_package_version_id
                == published.content_package_version_id,
                ContentDefinitionVersion.definition_key == "lesson.division.generate.output",
            )
        )
        assert definition is not None
        _seed_material_and_scope(session, actor, project.id, definition.id, case)
        nodes = LessonDivisionRuntimeService(session, actor).initialize(project.id)

    provider = DeterministicNodeOutputProvider(output)
    execution = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    committed = await execution.execute(
        nodes.generate_node_run_id,
        request_id="issue-125-generate",
    )

    with factory() as session, session.begin():
        validate_node_id = LessonDivisionRuntimeService(session, actor).stage_quality(
            committed.artifact_version_id
        )
    result = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, actor),
        runtime_quality_validator_registry(),
    ).execute(validate_node_id)
    assert result.conclusion == "passed"

    with factory() as session, session.begin():
        gate_id = LessonDivisionRuntimeService(session, actor).open_approval(
            committed.artifact_version_id
        )
        approval = ArtifactService(session, actor).review(
            committed.artifact_version_id,
            action="approve",
            comment="Approved lesson division",
            request_id="issue-125-approve",
        )

    with factory() as session:
        lessons = list(session.scalars(select(LessonUnit).order_by(LessonUnit.position)))
        assert [(lesson.lesson_key, lesson.status) for lesson in lessons] == [
            ("LESSON-001", "active")
        ]
        assert lessons[0].source_division_version_id == committed.artifact_version_id
        assert session.scalar(select(func.count()).select_from(LessonBranchConfig)) == 4
        assert session.scalar(select(func.count()).select_from(BranchRun)) == 4
        assert session.scalar(select(func.count()).select_from(NodeRun)) == 7
        assert session.get(NodeRun, nodes.generate_node_run_id).status == "review_required"
        assert session.get(NodeRun, validate_node_id).status == "approved"
        assert session.get(NodeRun, gate_id).status == "approved"
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 1
        assert session.get(Approval, approval.id).quality_evidence_json["report_id"] == str(
            result.report_id
        )
        event_types = list(
            session.scalars(
                select(EventStreamEntry.event_type).order_by(EventStreamEntry.sequence_no)
            )
        )
        assert "lesson.collection.synchronized" in event_types
        assert "workflow.lesson_branches.synchronized" in event_types
        assert "artifact.version.approved" in event_types


def _seed_material_and_scope(session, actor, project_id, definition_id, case) -> None:
    asset = FileAsset(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        asset_key=f"issue-125-material:{project_id}",
        asset_kind="source_material",
        current_version_id=None,
        status="active",
        retention_class="project",
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(asset)
    session.flush()
    file_version = FileAssetVersion(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        file_asset_id=asset.id,
        version_no=1,
        storage_bucket="test-only",
        storage_key=f"issue-125/{project_id}/material.pdf",
        mime_type="application/pdf",
        byte_size=1,
        sha256="a" * 64,
        etag="issue-125",
        width=None,
        height=None,
        duration_ms=None,
        page_count=3,
        scan_status="clean",
        metadata_json={},
        derived_from_version_id=None,
        created_at=utc_now(),
        created_by=actor.principal_id,
    )
    session.add(file_version)
    session.flush()
    asset.current_version_id = file_version.id
    material = SourceMaterial(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project_id,
        material_kind="textbook",
        file_asset_id=asset.id,
        original_filename="issue-125-material.pdf",
        mime_type="application/pdf",
        upload_status="confirmed",
        confirmed_at=utc_now(),
        confirmed_by=actor.principal_id,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(material)
    session.flush()
    material_content = {
        "source": case["source"],
        "material_evidence": case["material_evidence"],
        "knowledge_boundary": case["knowledge_boundary"],
    }
    parse = MaterialParseVersion(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        source_material_id=material.id,
        file_asset_version_id=file_version.id,
        generation_job_id=None,
        version_no=1,
        status="succeeded",
        parser_name="issue-125-fake",
        parser_version="1",
        content_json=material_content,
        page_count=3,
        text_checksum=canonical_content_hash(material_content),
        validation_report_json={"valid": True},
        error_code=None,
        created_at=utc_now(),
        started_at=utc_now(),
        completed_at=utc_now(),
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(parse)
    session.flush()
    scope_content = {
        "knowledge_point": "1-5",
        "material_evidence": case["material_evidence"],
        "knowledge_boundary": case["knowledge_boundary"],
    }
    scope = Artifact(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project_id,
        lesson_unit_id=None,
        branch_key="project",
        artifact_key="material-scope",
        artifact_type="material_scope",
        content_definition_version_id=definition_id,
        status="approved",
        stale_reason_json=None,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(scope)
    session.flush()
    scope_version = ArtifactVersion(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        artifact_id=scope.id,
        version_no=1,
        content_json=scope_content,
        content_hash=canonical_content_hash(scope_content),
        render_summary_json={},
        source_kind="manual",
        source_node_run_id=None,
        context_snapshot_id=None,
        prompt_snapshot_id=None,
        validation_report_json={"valid": True},
        created_by=actor.principal_id,
    )
    session.add(scope_version)
    session.flush()
    scope.current_approved_version_id = scope_version.id
