from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifact_quality.service import ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import SqlAlchemyArtifactQualityTransactionFactory
from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.models import Approval, Artifact, ArtifactRelation, ArtifactVersion
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.artifacts.service import ArtifactService
from apps.api.assets.execution_port import AssetExecutionPortError
from apps.api.assets.models import FileAsset, FileAssetVersion, MaterialParseVersion
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, system_actor
from apps.api.identity.models import ProjectMember
from apps.api.ids import new_uuid7
from apps.api.lessons.division_runtime import diff_lesson_divisions
from apps.api.lessons.models import LessonBranchConfig, LessonUnit
from apps.api.lessons.runtime_service import LessonDivisionRuntimeService
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.prompt_runtime.lesson_context_port import (
    LessonContextSnapshotReader,
    MaterialEvidenceSnapshot,
)
from apps.api.prompt_runtime.models import ContextSnapshot
from apps.api.reliability.models import EventStreamEntry
from apps.api.uploads.models import SourceMaterial
from apps.api.workflows.execution_port import (
    SqlAlchemyWorkflowExecutionPort,
    WorkflowExecutionPortError,
)
from apps.api.workflows.models import BranchRun, NodeInputSnapshot, NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import seed_test_actor

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


@dataclass(frozen=True, slots=True)
class PreparedApproval:
    actor: ActorContext
    project_id: UUID
    version_id: UUID
    generate_node_id: UUID
    validate_node_id: UUID
    gate_node_id: UUID
    report_id: UUID
    material_parse_version_id: UUID
    scope_version_id: UUID


async def test_generated_validated_approved_division_atomically_materializes_lesson_runtime(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    prepared = await _prepare_approval(factory, case, output)

    with factory() as session, session.begin():
        approval = ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="approve",
            comment="Approved lesson division",
            request_id="issue-125-approve",
        )

    with factory() as session:
        lessons = list(session.scalars(select(LessonUnit).order_by(LessonUnit.position)))
        assert [(lesson.lesson_key, lesson.status) for lesson in lessons] == [
            ("LESSON-001", "active")
        ]
        assert lessons[0].source_division_version_id == prepared.version_id
        assert session.scalar(select(func.count()).select_from(LessonBranchConfig)) == 4
        assert session.scalar(select(func.count()).select_from(BranchRun)) == 4
        assert session.scalar(select(func.count()).select_from(NodeRun)) == 7
        assert session.get(NodeRun, prepared.generate_node_id).status == "review_required"
        assert session.get(NodeRun, prepared.validate_node_id).status == "approved"
        assert session.get(NodeRun, prepared.gate_node_id).status == "approved"
        assert session.scalar(select(func.count()).select_from(ArtifactQualityReport)) == 1
        assert session.get(Approval, approval.id).quality_evidence_json["report_id"] == str(
            prepared.report_id
        )
        event_types = list(
            session.scalars(
                select(EventStreamEntry.event_type).order_by(EventStreamEntry.sequence_no)
            )
        )
        assert "lesson.collection.synchronized" in event_types
        assert "workflow.lesson_branches.synchronized" in event_types
        assert "artifact.version.approved" in event_types


async def test_stale_submitted_division_cannot_be_approved_or_materialized(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    prepared = await _prepare_approval(factory, case, output)

    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.scope_version_id,
            action="revoke",
            comment="The approved material scope was withdrawn.",
            request_id="issue-125-revoke-scope-before-approval",
        )

    with factory() as session:
        version = session.get(ArtifactVersion, prepared.version_id)
        assert version is not None
        division = session.get(Artifact, version.artifact_id)
        assert division is not None
        assert division.status == "stale"
        assert division.current_submitted_version_id == prepared.version_id
        assert session.get(NodeRun, prepared.gate_node_id).status == "review_required"
        session.rollback()

        with pytest.raises(ApiError) as caught:
            with session.begin():
                ArtifactService(session, prepared.actor).review(
                    prepared.version_id,
                    action="approve",
                    comment="Must not approve a stale submitted division.",
                    request_id="issue-125-reject-stale-submitted",
                )
        assert caught.value.code == "ARTIFACT_STATE_CONFLICT"
        session.rollback()

        assert session.scalar(select(func.count()).select_from(LessonUnit)) == 0
        assert session.scalar(select(func.count()).select_from(BranchRun)) == 0
        assert session.get(NodeRun, prepared.gate_node_id).status == "review_required"
        assert (
            session.scalar(
                select(func.count())
                .select_from(Approval)
                .where(
                    Approval.artifact_version_id == prepared.version_id,
                    Approval.action == "approve",
                )
            )
            == 0
        )


async def test_generation_freezes_approved_scope_and_teacher_constraints(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]

    prepared = await _prepare_approval(factory, case, output)

    with factory() as session:
        context = session.scalar(
            select(ContextSnapshot).where(ContextSnapshot.node_run_id == prepared.generate_node_id)
        )
        assert context is not None
        bindings = {
            binding["source"]: binding["items"] for binding in context.bindings_json["bindings"]
        }
        assert set(bindings) == {
            "material.approved_parse",
            "material_scope.approved_version",
        }
        scope = bindings["material_scope.approved_version"][0]["content"]
        assert scope["duration_minutes"] == 40
        assert scope["lesson_count_mode"] == "auto"
        assert scope["requested_lesson_count"] is None
        assert scope["lesson_type_preferences"] == ["new_learning"]
        assert scope["special_requirements"] == "Keep the approved knowledge boundary."
        assert scope["approved_evidence_keys"] == [
            "EV-MAT-01",
            "EV-MAT-02",
            "EV-MAT-03",
            "EV-MAT-04",
        ]


async def test_generation_selects_the_exact_parse_declared_by_approved_scope(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]

    prepared = await _prepare_approval(factory, case, output, add_second_parse=True)

    with factory() as session:
        context = session.scalar(
            select(ContextSnapshot).where(ContextSnapshot.node_run_id == prepared.generate_node_id)
        )
        assert context is not None
        bindings = {
            binding["source"]: binding["items"] for binding in context.bindings_json["bindings"]
        }
        material_items = bindings["material.approved_parse"]
        assert len(material_items) == 1
        assert material_items[0]["source_version_id"] == str(prepared.material_parse_version_id)


async def test_missing_exact_parse_selection_fails_before_provider_or_audit_facts(
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
            CreateProjectRequest(title="Invalid exact parse scope", knowledge_point="1-5")
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
            include_exact_parse_binding=False,
            add_second_parse=True,
        )
        nodes = LessonDivisionRuntimeService(session, actor).initialize(project.id)

    provider = DeterministicNodeOutputProvider(output)
    execution = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(AssetExecutionPortError) as caught:
        await execution.execute(
            nodes.generate_node_run_id,
            request_id="issue-125-missing-exact-parse",
        )
    assert caught.value.code == "NODE_EXECUTION_MATERIAL_SCOPE_INVALID"
    assert provider.calls == 0

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(GenerationAttempt)) == 0
        assert session.scalar(select(func.count()).select_from(UsageRecord)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(Artifact)
                .where(Artifact.artifact_type == "lesson_division")
            )
            == 0
        )


async def test_quality_coverage_uses_exact_approved_scope_not_the_whole_parse(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    output["lesson_units"][0]["evidence_refs"] = ["EV-MAT-01"]

    prepared = await _prepare_approval(
        factory,
        case,
        output,
        approved_evidence_keys=("EV-MAT-01",),
    )

    with factory() as session:
        report = session.get(ArtifactQualityReport, prepared.report_id)
        assert report is not None
        assert report.conclusion == "passed"


async def test_completion_failure_rolls_back_approval_lessons_fanout_and_events(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    prepared = await _prepare_approval(factory, case, output)

    def fail_fanout(*_args, **_kwargs):
        raise RuntimeError("fanout fault")

    monkeypatch.setattr(
        "apps.api.workflows.lesson_fanout.LessonWorkflowFanoutService.synchronize_declared_approval",
        fail_fanout,
    )
    with factory() as session:
        with pytest.raises(RuntimeError, match="fanout fault"):
            with session.begin():
                ArtifactService(session, prepared.actor).review(
                    prepared.version_id,
                    action="approve",
                    comment="Must roll back",
                    request_id="issue-125-fault",
                )

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(LessonUnit)) == 0
        assert session.scalar(select(func.count()).select_from(BranchRun)) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(Approval)
                .where(Approval.artifact_version_id == prepared.version_id)
            )
            == 1
        )
        assert session.get(NodeRun, prepared.gate_node_id).status == "review_required"
        assert (
            session.scalar(
                select(func.count())
                .select_from(EventStreamEntry)
                .where(EventStreamEntry.event_type == "lesson.collection.synchronized")
            )
            == 0
        )


async def test_cross_project_context_snapshot_is_rejected_before_quality_staging(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    prepared = await _prepare_approval(factory, case, output)

    monkeypatch.setattr(
        LessonContextSnapshotReader,
        "material_evidence",
        lambda *_args: MaterialEvidenceSnapshot(
            project_id=new_uuid7(),
            node_run_id=prepared.generate_node_id,
            source_material_id=new_uuid7(),
            material_parse_version_id=new_uuid7(),
        ),
    )

    with factory() as session:
        with pytest.raises(ApiError) as captured:
            with session.begin():
                LessonDivisionRuntimeService(session, prepared.actor).stage_quality(
                    prepared.version_id
                )
        assert captured.value.code == "LESSON_DIVISION_RUNTIME_INVALID"
        assert (
            session.scalar(
                select(func.count())
                .select_from(NodeInputSnapshot)
                .where(NodeInputSnapshot.node_run_id == prepared.validate_node_id)
            )
            == 3
        )


async def test_extra_lesson_with_active_execution_blocks_atomic_archive(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    prepared = await _prepare_approval(factory, case, output)

    with factory() as session, session.begin():
        generate = session.get(NodeRun, prepared.generate_node_id)
        assert generate is not None
        extra = LessonUnit(
            id=new_uuid7(),
            organization_id=prepared.actor.organization_id,
            project_id=prepared.project_id,
            lesson_key="EXTRA-DRIFTED-LESSON",
            position=2,
            title="Drifted lesson",
            scope_summary="Not present in the approved division",
            objective_summary="Must not archive while execution is active",
            estimated_minutes=40,
            source_division_version_id=prepared.version_id,
            status="active",
            created_by=prepared.actor.principal_id,
            updated_by=prepared.actor.principal_id,
        )
        session.add(extra)
        session.flush()
        branch = BranchRun(
            id=new_uuid7(),
            workflow_run_id=generate.workflow_run_id,
            lesson_unit_id=extra.id,
            branch_key="lesson_plan",
            status="active",
            started_at=utc_now(),
            created_by=prepared.actor.principal_id,
            updated_by=prepared.actor.principal_id,
        )
        session.add(branch)
        session.flush()
        active_node_id = new_uuid7()
        active_node = NodeRun(
            id=active_node_id,
            organization_id=prepared.actor.organization_id,
            workflow_run_id=generate.workflow_run_id,
            branch_run_id=branch.id,
            node_key="lesson_plan.generate",
            run_no=1,
            status="queued",
            trigger_type="manual",
            automation_policy_snapshot_json=generate.automation_policy_snapshot_json,
            created_by=prepared.actor.principal_id,
            updated_by=prepared.actor.principal_id,
        )
        session.add(active_node)

    with factory() as session:
        with pytest.raises(ApiError) as captured:
            with session.begin():
                ArtifactService(session, prepared.actor).review(
                    prepared.version_id,
                    action="approve",
                    comment="Must reject the drifted active lesson",
                    request_id="issue-125-extra-active-archive",
                )
        assert captured.value.code == "LESSON_ARCHIVE_EXECUTION_ACTIVE"
        extra = session.scalar(
            select(LessonUnit).where(LessonUnit.lesson_key == "EXTRA-DRIFTED-LESSON")
        )
        assert extra is not None and extra.status == "active"
        assert session.get(NodeRun, active_node_id).status == "queued"


async def test_concurrent_double_approval_materializes_one_lesson_runtime(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    prepared = await _prepare_approval(factory, case, output)

    def approve(request_id: str) -> UUID:
        with factory() as session, session.begin():
            return (
                ArtifactService(session, prepared.actor)
                .review(
                    prepared.version_id,
                    action="approve",
                    comment="Concurrent approval",
                    request_id=request_id,
                )
                .id
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        approval_ids = list(executor.map(approve, ("issue-125-double-1", "issue-125-double-2")))

    assert approval_ids[0] == approval_ids[1]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(LessonUnit)) == 1
        assert session.scalar(select(func.count()).select_from(BranchRun)) == 4
        assert (
            session.scalar(
                select(func.count())
                .select_from(Approval)
                .where(
                    Approval.artifact_version_id == prepared.version_id,
                    Approval.action == "approve",
                )
            )
            == 1
        )


@pytest.mark.parametrize("approval_actor", ["reviewer", "system"])
async def test_declared_completion_accepts_review_authority_without_edit_permission(
    migrated_database_url: str,
    approval_actor: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    prepared = await _prepare_approval(factory, case, output)

    with factory() as session, session.begin():
        if approval_actor == "system":
            actor = system_actor(prepared.actor.organization_id)
        else:
            reviewer = seed_test_actor(
                session,
                organization_id=prepared.actor.organization_id,
                user_id=UUID("01900000-0000-7000-8000-000000001251"),
                principal_id=UUID("01900000-0000-7000-8000-000000001252"),
                member_id=UUID("01900000-0000-7000-8000-000000001253"),
                email="issue-125-reviewer@example.test",
                display_name="Issue 125 Reviewer",
            )
            assert reviewer.user_id is not None
            session.add(
                ProjectMember(
                    id=new_uuid7(),
                    project_id=prepared.project_id,
                    user_id=reviewer.user_id,
                    role="reviewer",
                    created_at=utc_now(),
                )
            )
            session.flush()
            actor = reviewer

        ArtifactService(session, actor).review(
            prepared.version_id,
            action="approve",
            comment="Approve with review authority",
            request_id=f"issue-125-{approval_actor}-approval",
        )

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(LessonUnit)) == 1
        assert session.get(NodeRun, prepared.gate_node_id).status == "approved"


async def test_revision_reuses_stable_ids_and_stales_only_changed_or_archived_lessons(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    base = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    first_output = _four_lesson_output(base)
    prepared = await _prepare_approval(factory, case, first_output)
    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="approve",
            comment="Approve first division",
            request_id="issue-125-first-approval",
        )
        first_lessons = {
            lesson.lesson_key: lesson.id
            for lesson in session.scalars(select(LessonUnit).order_by(LessonUnit.lesson_key))
        }
        downstream = _seed_keyed_downstream_artifacts(
            session,
            prepared,
            first_lessons,
        )
    with factory() as session:
        relations = list(
            session.scalars(
                select(ArtifactRelation).where(
                    ArtifactRelation.from_artifact_version_id == prepared.version_id
                )
            )
        )
        assert len(relations) == 3
        assert all(
            session.get(Artifact, artifact_id).current_approved_version_id is not None
            for artifact_id in downstream.values()
        )

    second_output = deepcopy(first_output)
    units = second_output["lesson_units"]
    by_key = {unit["lesson_unit_key"]: unit for unit in units}
    by_key["LESSON-01"]["core_learning_outcome"] = "Materially changed outcome"
    by_key["LESSON-03"]["position"] = 2
    by_key["LESSON-04"]["position"] = 3
    added = deepcopy(by_key["LESSON-02"])
    added["lesson_unit_key"] = "LESSON-05"
    added["position"] = 4
    added["title"] = "Replacement lesson"
    second_output["lesson_units"] = [
        by_key["LESSON-01"],
        by_key["LESSON-03"],
        by_key["LESSON-04"],
        added,
    ]
    second_output["lesson_count"] = 4
    expected_diff = diff_lesson_divisions(first_output, second_output)
    assert expected_diff.changed_keys == ("LESSON-01",)
    assert expected_diff.archived_keys == ("LESSON-02",)
    assert expected_diff.unchanged_keys == ("LESSON-03", "LESSON-04")

    second_version_id = await _execute_revision(factory, prepared, second_output)

    with factory() as session:
        lessons = list(session.scalars(select(LessonUnit).order_by(LessonUnit.lesson_key)))
        lesson_by_key = {lesson.lesson_key: lesson for lesson in lessons}
        assert lesson_by_key["LESSON-01"].id == first_lessons["LESSON-01"]
        assert lesson_by_key["LESSON-03"].id == first_lessons["LESSON-03"]
        assert lesson_by_key["LESSON-04"].id == first_lessons["LESSON-04"]
        assert lesson_by_key["LESSON-02"].status == "archived"
        assert lesson_by_key["LESSON-05"].status == "active"
        assert lesson_by_key["LESSON-01"].source_division_version_id == second_version_id
        stale_event = session.scalar(
            select(EventStreamEntry)
            .where(EventStreamEntry.event_type == "artifact.version.approved")
            .order_by(EventStreamEntry.sequence_no.desc())
            .limit(1)
        )
        assert stale_event is not None
        assert session.get(Artifact, downstream["LESSON-01"]).status == "stale", (
            stale_event.summary_json
        )
        assert session.get(Artifact, downstream["LESSON-02"]).status == "stale"
        assert session.get(Artifact, downstream["LESSON-03"]).status == "approved"


async def test_unchanged_relation_carries_forward_then_stales_on_third_version_change(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    base = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    first_output = _four_lesson_output(base)
    prepared = await _prepare_approval(factory, case, first_output)
    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="approve",
            comment="Approve v1",
            request_id="issue-125-carry-v1",
        )
        lesson_ids = {
            lesson.lesson_key: lesson.id
            for lesson in session.scalars(select(LessonUnit).order_by(LessonUnit.lesson_key))
        }
        downstream = _seed_keyed_downstream_artifacts(session, prepared, lesson_ids)

    second_output = deepcopy(first_output)
    second_output["lesson_units"][2]["position"] = 4
    second_output["lesson_units"][3]["position"] = 3
    second_version_id = await _execute_revision(factory, prepared, second_output)

    with factory() as session:
        target_version_id = session.get(
            Artifact,
            downstream["LESSON-03"],
        ).current_approved_version_id
        carried = session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.from_artifact_version_id == second_version_id,
                ArtifactRelation.to_artifact_version_id == target_version_id,
            )
        )
        assert carried is not None
        assert carried.impact_scope_json == {
            "mode": "keyed",
            "selector": "lesson_key",
            "keys": ["LESSON-03"],
        }

    third_output = deepcopy(second_output)
    third_output["lesson_units"][2]["core_learning_outcome"] = "Changed on version three"
    await _execute_revision(factory, prepared, third_output)

    with factory() as session:
        assert session.get(Artifact, downstream["LESSON-03"]).status == "stale"


async def test_archived_stable_key_readd_reuses_lesson_but_not_old_node_run(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    base = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    first_output = _four_lesson_output(base)
    prepared = await _prepare_approval(factory, case, first_output)
    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="approve",
            comment="Approve lifecycle v1",
            request_id="issue-125-lifecycle-v1",
        )
        lesson = session.scalar(select(LessonUnit).where(LessonUnit.lesson_key == "LESSON-02"))
        assert lesson is not None
        lesson_id = lesson.id
        branch = session.scalar(
            select(BranchRun).where(
                BranchRun.lesson_unit_id == lesson_id,
                BranchRun.branch_key == "lesson_plan",
            )
        )
        assert branch is not None
        branch_id = branch.id
        old_node = session.scalar(
            select(NodeRun).where(
                NodeRun.branch_run_id == branch_id,
                NodeRun.node_key == "lesson_plan.generate",
            )
        )
        assert old_node is not None and old_node.status == "ready"
        old_node_id = old_node.id

    second_output = deepcopy(first_output)
    second_output["lesson_units"][1]["lesson_unit_key"] = "LESSON-05"
    second_output["lesson_units"][1]["title"] = "Temporary replacement"
    await _execute_revision(factory, prepared, second_output)

    with factory() as session:
        lesson = session.get(LessonUnit, lesson_id)
        branch = session.get(BranchRun, branch_id)
        assert lesson is not None and lesson.status == "archived"
        assert branch is not None and branch.status == "cancelled"

    third_output = deepcopy(second_output)
    third_output["lesson_units"][1] = deepcopy(first_output["lesson_units"][1])
    await _execute_revision(factory, prepared, third_output)

    with factory() as session:
        lesson = session.scalar(select(LessonUnit).where(LessonUnit.lesson_key == "LESSON-02"))
        branch = session.scalar(
            select(BranchRun).where(
                BranchRun.lesson_unit_id == lesson_id,
                BranchRun.branch_key == "lesson_plan",
            )
        )
        nodes = list(
            session.scalars(
                select(NodeRun)
                .where(
                    NodeRun.branch_run_id == branch_id,
                    NodeRun.node_key == "lesson_plan.generate",
                )
                .order_by(NodeRun.run_no)
            )
        )
        assert lesson is not None and lesson.id == lesson_id and lesson.status == "active"
        assert branch is not None and branch.id == branch_id and branch.status == "active"
        assert [(node.run_no, node.status) for node in nodes] == [
            (1, "disabled"),
            (2, "ready"),
        ]
        with pytest.raises(WorkflowExecutionPortError) as caught:
            SqlAlchemyWorkflowExecutionPort(session, prepared.actor).start(old_node_id)
        assert caught.value.code == "NODE_EXECUTION_STATE_CONFLICT"


async def _execute_revision(
    factory: sessionmaker[Session],
    prepared: PreparedApproval,
    output: dict[str, object],
) -> UUID:
    with factory() as session, session.begin():
        nodes = LessonDivisionRuntimeService(session, prepared.actor).initialize_revision(
            prepared.project_id
        )
    committed = await NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, prepared.actor),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(output)
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    ).execute(nodes.generate_node_run_id, request_id="issue-125-revision-generate")
    with factory() as session, session.begin():
        validate_id = LessonDivisionRuntimeService(session, prepared.actor).stage_quality(
            committed.artifact_version_id
        )
    quality = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, prepared.actor),
        runtime_quality_validator_registry(),
    ).execute(validate_id)
    assert quality.conclusion == "passed"
    with factory() as session, session.begin():
        LessonDivisionRuntimeService(session, prepared.actor).open_approval(
            committed.artifact_version_id
        )
        ArtifactService(session, prepared.actor).review(
            committed.artifact_version_id,
            action="approve",
            comment="Approve revision",
            request_id="issue-125-revision-approve",
        )
    return committed.artifact_version_id


def _four_lesson_output(base: dict[str, object]) -> dict[str, object]:
    output = deepcopy(base)
    source = output["lesson_units"][0]
    units = []
    for position in range(1, 5):
        unit = deepcopy(source)
        unit["lesson_unit_key"] = f"LESSON-{position:02d}"
        unit["position"] = position
        unit["title"] = f"Lesson {position}"
        unit["core_learning_outcome"] = f"Observable outcome {position}"
        unit["material_scope"] = f"Approved scope {position}"
        unit["evidence_refs"] = [f"EV-MAT-0{position}"]
        units.append(unit)
    output["lesson_units"] = units
    output["lesson_count"] = len(units)
    return output


def _seed_keyed_downstream_artifacts(
    session: Session,
    prepared: PreparedApproval,
    lesson_ids: dict[str, UUID],
) -> dict[str, UUID]:
    source = session.get(ArtifactVersion, prepared.version_id)
    assert source is not None
    definition_id = session.scalar(
        select(ContentDefinitionVersion.id).where(
            ContentDefinitionVersion.definition_key == "lesson_plan.generate.output"
        )
    )
    assert definition_id is not None
    artifact_ids: dict[str, UUID] = {}
    for lesson_key in ("LESSON-01", "LESSON-02", "LESSON-03"):
        artifact = Artifact(
            id=new_uuid7(),
            organization_id=prepared.actor.organization_id,
            project_id=prepared.project_id,
            lesson_unit_id=lesson_ids[lesson_key],
            branch_key="lesson_plan",
            artifact_key=f"lesson-plan:{lesson_key}",
            artifact_type="lesson_plan",
            content_definition_version_id=definition_id,
            status="approved",
            stale_reason_json=None,
            created_by=prepared.actor.principal_id,
            updated_by=prepared.actor.principal_id,
        )
        session.add(artifact)
        session.flush()
        content = {"source_lesson_unit_key": lesson_key}
        version = ArtifactVersion(
            id=new_uuid7(),
            organization_id=prepared.actor.organization_id,
            artifact_id=artifact.id,
            version_no=1,
            content_json=content,
            content_hash=canonical_content_hash(content),
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=prepared.actor.principal_id,
        )
        session.add(version)
        session.flush()
        artifact.current_approved_version_id = version.id
        session.flush()
        ArtifactRelationService(session, prepared.actor).add(
            from_version_id=source.id,
            to_version_id=version.id,
            relation_type="derives_from",
            binding_key="upstream.approval.lesson_division",
            impact_scope={
                "mode": "keyed",
                "selector": "lesson_key",
                "keys": [lesson_key],
            },
        )
        artifact_ids[lesson_key] = artifact.id
    return artifact_ids


async def _prepare_approval(
    factory: sessionmaker[Session],
    case,
    output: dict[str, object],
    *,
    approved_evidence_keys: tuple[str, ...] | None = None,
    add_second_parse: bool = False,
) -> PreparedApproval:
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
        material_parse_version_id, scope_version_id = _seed_material_and_scope(
            session,
            actor,
            project.id,
            definition.id,
            case,
            approved_evidence_keys=approved_evidence_keys,
            add_second_parse=add_second_parse,
        )
        nodes = LessonDivisionRuntimeService(session, actor).initialize(project.id)
    execution = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, actor),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(output)
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    committed = await execution.execute(
        nodes.generate_node_run_id,
        request_id="issue-125-generate",
    )
    with factory() as session, session.begin():
        validate_id = LessonDivisionRuntimeService(session, actor).stage_quality(
            committed.artifact_version_id
        )
        replayed_validate_id = LessonDivisionRuntimeService(session, actor).stage_quality(
            committed.artifact_version_id
        )
        assert replayed_validate_id == validate_id
        assert (
            session.scalar(
                select(func.count())
                .select_from(NodeInputSnapshot)
                .where(NodeInputSnapshot.node_run_id == validate_id)
            )
            == 3
        )
    quality = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, actor),
        runtime_quality_validator_registry(),
    ).execute(validate_id)
    assert quality.conclusion == "passed"
    with factory() as session, session.begin():
        gate_id = LessonDivisionRuntimeService(session, actor).open_approval(
            committed.artifact_version_id
        )
    return PreparedApproval(
        actor=actor,
        project_id=project.id,
        version_id=committed.artifact_version_id,
        generate_node_id=nodes.generate_node_run_id,
        validate_node_id=validate_id,
        gate_node_id=gate_id,
        report_id=quality.report_id,
        material_parse_version_id=material_parse_version_id,
        scope_version_id=scope_version_id,
    )


def _seed_material_and_scope(
    session,
    actor,
    project_id,
    definition_id,
    case,
    *,
    approved_evidence_keys: tuple[str, ...] | None,
    include_exact_parse_binding: bool = True,
    add_second_parse: bool = False,
) -> tuple[UUID, UUID]:
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
    if add_second_parse:
        second_content = deepcopy(material_content)
        second_content["parse_revision"] = 2
        session.add(
            MaterialParseVersion(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                source_material_id=material.id,
                file_asset_version_id=file_version.id,
                generation_job_id=None,
                version_no=2,
                status="succeeded",
                parser_name="issue-125-fake",
                parser_version="2",
                content_json=second_content,
                page_count=3,
                text_checksum=canonical_content_hash(second_content),
                validation_report_json={"valid": True},
                error_code=None,
                created_at=utc_now(),
                started_at=utc_now(),
                completed_at=utc_now(),
                created_by=actor.principal_id,
                updated_by=actor.principal_id,
            )
        )
    scope_content = {
        "knowledge_point": "1-5",
        "knowledge_boundary": case["knowledge_boundary"],
        "approved_evidence_keys": list(
            approved_evidence_keys
            or tuple(item["evidence_key"] for item in case["material_evidence"])
        ),
        "duration_minutes": 40,
        "lesson_count_mode": "auto",
        "requested_lesson_count": None,
        "lesson_type_preferences": ["new_learning"],
        "special_requirements": "Keep the approved knowledge boundary.",
    }
    if include_exact_parse_binding:
        scope_content.update(
            {
                "source_material_id": str(material.id),
                "material_parse_version_id": str(parse.id),
            }
        )
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
    return parse.id, scope_version.id
