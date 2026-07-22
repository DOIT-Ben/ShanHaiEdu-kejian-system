from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.authoring_provision import (
    ArtifactAuthoringProvisionPort,
    GeneratedDraftRequest,
)
from apps.api.artifacts.models import Artifact, ArtifactRelation, ArtifactVersion
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.context import ActorContext, system_actor
from apps.api.identity.models import ProjectMember
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonUnit
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.projects.models import Project
from apps.api.workflows.models import (
    NodeInputSnapshot,
    NodeRun,
    WorkflowDefinitionVersion,
    WorkflowRun,
)
from apps.api.workflows.service import WorkflowRuntimeService
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import seed_test_actor
from tests.integration.test_lesson_plan_runtime import (
    PreparedLessonPlan,
    _open_gate,  # pyright: ignore[reportPrivateUsage]
    _prepare_generated_lesson_plan,  # pyright: ignore[reportPrivateUsage]
    _stage_and_validate,  # pyright: ignore[reportPrivateUsage]
)
from workflow.node_state import NodeStatus

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


async def test_editor_can_submit_replacement_and_retire_existing_gate(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _prepare_generated_lesson_plan(factory)
    _stage_and_validate(factory, prepared.actor, prepared.version_id)
    gate_id = _open_gate(factory, prepared.actor, prepared.version_id)
    content, lock_version = _open_generated_draft(factory, prepared)
    editor = _seed_editor(factory, prepared)
    content["teaching_content"]["lesson_topic"] = "1~5的认识与多种表征"

    with factory() as session, session.begin():
        service = ArtifactService(session, editor)
        saved = service.save_draft(
            prepared.artifact_id,
            "main",
            expected_lock_version=lock_version,
            content=content,
            request_id="issue-126-editor-save-replacement",
        )
        replacement = service.submit(
            prepared.artifact_id,
            "main",
            expected_lock_version=saved.lock_version,
            source_kind="manual",
            request_id="issue-126-editor-submit-replacement",
        )

    with factory() as session:
        artifact = session.get(Artifact, prepared.artifact_id)
        gate = session.get(NodeRun, gate_id)
        assert artifact is not None and gate is not None
        assert artifact.current_submitted_version_id == replacement.id
        assert gate.status == "skipped"


async def test_manual_replacement_inherits_division_relation_and_stales_on_revoke(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _prepare_generated_lesson_plan(factory)
    previous_division_id, current_division_id = _carry_division_forward(
        factory,
        prepared,
    )
    _stage_and_validate(factory, prepared.actor, prepared.version_id)
    _open_gate(factory, prepared.actor, prepared.version_id)
    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="request_changes",
            comment="Return the generated lesson plan before manual repair.",
            request_id="issue-126-return-before-lineage-repair",
        )
    content, lock_version = _open_generated_draft(factory, prepared)
    content["teaching_content"]["lesson_topic"] = "1~5的认识与多种表征"

    with factory() as session, session.begin():
        service = ArtifactService(session, prepared.actor)
        saved = service.save_draft(
            prepared.artifact_id,
            "main",
            expected_lock_version=lock_version,
            content=content,
            request_id="issue-126-owner-save-replacement",
        )
        replacement = service.submit(
            prepared.artifact_id,
            "main",
            expected_lock_version=saved.lock_version,
            source_kind="manual",
            request_id="issue-126-owner-submit-replacement",
        )
        replacement_id = replacement.id

    _stage_and_validate(factory, prepared.actor, replacement_id)
    _open_gate(factory, prepared.actor, replacement_id)
    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            replacement_id,
            action="approve",
            comment="Approve the replacement before revoking its division source.",
            request_id="issue-126-approve-manual-replacement",
        )

    with factory() as session:
        lesson = session.scalar(
            select(LessonUnit).where(LessonUnit.organization_id == prepared.actor.organization_id)
        )
        assert lesson is not None
        division_version_id = lesson.source_division_version_id
        assert division_version_id == current_division_id
        relation = session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.from_artifact_version_id == division_version_id,
                ArtifactRelation.to_artifact_version_id == replacement_id,
                ArtifactRelation.relation_type != "supersedes",
            )
        )
        assert relation is not None
        historical_relation = session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.from_artifact_version_id == previous_division_id,
                ArtifactRelation.to_artifact_version_id == replacement_id,
                ArtifactRelation.relation_type != "supersedes",
            )
        )
        assert historical_relation is None

    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            division_version_id,
            action="revoke",
            comment="Withdraw the exact division used by the replacement.",
            request_id="issue-126-revoke-manual-replacement-source",
        )

    with factory() as session:
        artifact = session.get(Artifact, prepared.artifact_id)
        assert artifact is not None
        assert artifact.status == "stale"


async def test_model_regeneration_retires_previous_exact_gate(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _prepare_generated_lesson_plan(factory)
    previous_division_id, current_division_id = _carry_division_forward(
        factory,
        prepared,
    )
    _stage_and_validate(factory, prepared.actor, prepared.version_id)
    gate_id = _open_gate(factory, prepared.actor, prepared.version_id)

    with factory() as session, session.begin():
        first = session.get(NodeRun, prepared.generate_node_id)
        assert first is not None and first.branch_run_id is not None
        replacement_node = WorkflowRuntimeService(session, prepared.actor).create_branch_node_run(
            first.workflow_run_id,
            first.branch_run_id,
            node_key=first.node_key,
            status=NodeStatus.READY,
        )
        replacement_node_id = replacement_node.id

    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = deepcopy(build_golden_branch_source_outputs(case)["lesson_plan.generate"])
    output["teaching_content"]["lesson_topic"] = "1~5的认识与多种表征"
    replacement = await NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, prepared.actor),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(output)
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    ).execute(replacement_node_id, request_id="issue-126-model-regenerate")

    with factory() as session:
        artifact = session.get(Artifact, prepared.artifact_id)
        gate = session.get(NodeRun, gate_id)
        assert artifact is not None and gate is not None
        assert replacement.artifact_version_id != prepared.version_id
        assert artifact.current_submitted_version_id == replacement.artifact_version_id
        assert gate.status == "skipped"
        current_relation = session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.from_artifact_version_id == current_division_id,
                ArtifactRelation.to_artifact_version_id == replacement.artifact_version_id,
                ArtifactRelation.relation_type != "supersedes",
            )
        )
        historical_relation = session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.from_artifact_version_id == previous_division_id,
                ArtifactRelation.to_artifact_version_id == replacement.artifact_version_id,
                ArtifactRelation.relation_type != "supersedes",
            )
        )
        assert current_relation is not None
        assert historical_relation is None


async def test_gate_snapshot_uses_published_quality_report_ref(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _prepare_generated_lesson_plan(factory)
    replacement_ref = "report:intro_quality"

    with factory() as session, session.begin():
        generate = session.get(NodeRun, prepared.generate_node_id)
        assert generate is not None
        run = session.get(WorkflowRun, generate.workflow_run_id)
        assert run is not None
        workflow = session.get(
            WorkflowDefinitionVersion,
            run.workflow_definition_version_id,
        )
        assert workflow is not None
        graph = deepcopy(workflow.graph_json)
        for node in graph["nodes"]:
            if node["node_key"] == "lesson_plan.validate":
                node["output_contract_refs"] = [replacement_ref]
                node["quality_report_persistence"]["report_ref"] = replacement_ref
            elif node["node_key"] == "lesson_plan.approve":
                node["input_contract_refs"] = ["artifact:lesson_plan", replacement_ref]
                node["quality_requirement"]["report_refs"] = [replacement_ref]
        encoded = json.dumps(
            graph,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        replacement_workflow = WorkflowDefinitionVersion(
            id=new_uuid7(),
            workflow_definition_id=workflow.workflow_definition_id,
            version_no=workflow.version_no + 1,
            graph_json=graph,
            input_contract_json=workflow.input_contract_json,
            status="published",
            checksum=sha256(encoded).hexdigest(),
            published_at=utc_now(),
        )
        session.add(replacement_workflow)
        session.flush()
        artifact = session.get(Artifact, prepared.artifact_id)
        assert artifact is not None
        project = session.get(Project, artifact.project_id)
        assert project is not None
        project.workflow_definition_version_id = replacement_workflow.id
        run.workflow_definition_version_id = replacement_workflow.id

    validate_id, _ = _stage_and_validate(factory, prepared.actor, prepared.version_id)
    gate_id = _open_gate(factory, prepared.actor, prepared.version_id)

    with factory() as session:
        report_snapshot = session.scalar(
            select(NodeInputSnapshot).where(
                NodeInputSnapshot.node_run_id == gate_id,
                NodeInputSnapshot.input_key == replacement_ref,
            )
        )
        hardcoded = session.scalar(
            select(NodeInputSnapshot).where(
                NodeInputSnapshot.node_run_id == gate_id,
                NodeInputSnapshot.input_key == "report:lesson_plan_quality",
            )
        )
        assert validate_id is not None
        assert report_snapshot is not None
        assert hardcoded is None


def _open_generated_draft(
    factory: sessionmaker[Session],
    prepared: PreparedLessonPlan,
) -> tuple[dict[str, Any], int]:
    with factory() as session, session.begin():
        version = session.get(ArtifactVersion, prepared.version_id)
        assert version is not None
        draft = ArtifactAuthoringProvisionPort(
            session,
            system_actor(prepared.actor.organization_id),
        ).open_generated_draft(
            GeneratedDraftRequest(
                artifact_id=prepared.artifact_id,
                artifact_version_id=version.id,
                expected_content_hash=version.content_hash,
                draft_branch="main",
            )
        )
        return deepcopy(version.content_json), draft.lock_version


def _carry_division_forward(
    factory: sessionmaker[Session],
    prepared: PreparedLessonPlan,
) -> tuple[UUID, UUID]:
    with factory() as session, session.begin():
        lesson = session.scalar(
            select(LessonUnit).where(LessonUnit.organization_id == prepared.actor.organization_id)
        )
        assert lesson is not None
        previous = session.get(ArtifactVersion, lesson.source_division_version_id)
        assert previous is not None
        division = session.get(Artifact, previous.artifact_id)
        assert division is not None
        previous_relation = session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.from_artifact_version_id == previous.id,
                ArtifactRelation.to_artifact_version_id == prepared.version_id,
                ArtifactRelation.relation_type != "supersedes",
            )
        )
        assert previous_relation is not None
        current = ArtifactVersion(
            id=new_uuid7(),
            organization_id=previous.organization_id,
            artifact_id=previous.artifact_id,
            version_no=previous.version_no + 1,
            content_json=deepcopy(previous.content_json),
            content_hash=previous.content_hash,
            render_summary_json=dict(previous.render_summary_json),
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=previous.context_snapshot_id,
            prompt_snapshot_id=None,
            validation_report_json=dict(previous.validation_report_json),
            created_by=prepared.actor.principal_id,
        )
        session.add(current)
        session.flush()
        division.current_approved_version_id = current.id
        lesson.source_division_version_id = current.id
        session.flush()
        ArtifactRelationService(session, prepared.actor).add(
            from_version_id=current.id,
            to_version_id=prepared.version_id,
            relation_type=previous_relation.relation_type,
            binding_key=previous_relation.binding_key,
            impact_scope=previous_relation.impact_scope_json,
        )
        return previous.id, current.id


def _seed_editor(
    factory: sessionmaker[Session],
    prepared: PreparedLessonPlan,
) -> ActorContext:
    with factory() as session, session.begin():
        artifact = session.get(Artifact, prepared.artifact_id)
        assert artifact is not None
        editor = seed_test_actor(
            session,
            organization_id=prepared.actor.organization_id,
            user_id=UUID("01900000-0000-7000-8000-000000001261"),
            principal_id=UUID("01900000-0000-7000-8000-000000001262"),
            member_id=UUID("01900000-0000-7000-8000-000000001263"),
            email="issue-126-editor@example.test",
            display_name="Issue 126 Editor",
        )
        assert editor.user_id is not None
        session.add(
            ProjectMember(
                id=new_uuid7(),
                project_id=artifact.project_id,
                user_id=editor.user_id,
                role="editor",
                created_at=utc_now(),
            )
        )
        return editor
