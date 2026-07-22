from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.service import ArtifactQualityService
from apps.api.artifact_quality.sqlalchemy import SqlAlchemyArtifactQualityTransactionFactory
from apps.api.artifacts.models import Approval, Artifact, ArtifactRelation, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, system_actor
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.intro_options.quality import intro_runtime_quality_validator_registry
from apps.api.intro_options.runtime import IntroOptionRuntimeService
from apps.api.lessons.models import LessonUnit
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.prompt_runtime.models import ContextSnapshot
from apps.api.reliability.models import EventStreamEntry
from apps.api.workflows.models import NodeRun
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.integration.test_lesson_division_runtime import (
    _prepare_approval,  # pyright: ignore[reportPrivateUsage, reportUnknownVariableType]
)
from workflow.model_capabilities import ModelCapability

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


@dataclass(frozen=True, slots=True)
class PreparedIntroOption:
    actor: ActorContext
    project_id: UUID
    lesson_unit_id: UUID
    artifact_id: UUID
    version_id: UUID
    generate_node_id: UUID


async def test_default_nine_runs_exact_postgres_quality_and_approval_chain(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _generate_default_nine(factory)
    validate_id, report_id = _validate(factory, prepared.actor, prepared.version_id)
    gate_id = _open_gate(factory, prepared.actor, prepared.version_id)

    with factory() as session, session.begin():
        approval = ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="approve",
            comment="Approve the exact nine-option set.",
            request_id="issue-127-approve-default-nine",
        )

    with factory() as session:
        version = session.get(ArtifactVersion, prepared.version_id)
        artifact = session.get(Artifact, prepared.artifact_id)
        validate = session.get(NodeRun, validate_id)
        gate = session.get(NodeRun, gate_id)
        record = session.get(Approval, approval.id)
        assert version is not None and artifact is not None
        assert validate is not None and gate is not None and record is not None
        assert version.content_json["generation_mode"] == "default_nine"
        assert version.content_json["source_intro_option_version_refs"] == []
        assert len(version.content_json["options"]) == 9
        assert artifact.current_approved_version_id == version.id
        assert validate.status == "approved"
        assert gate.status == "approved"
        assert record.quality_evidence_json["report_id"] == str(report_id)
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactRelation)
                .where(
                    ArtifactRelation.to_artifact_version_id == version.id,
                    ArtifactRelation.binding_key == "upstream.artifact.intro_option_set_source",
                )
            )
            == 0
        )


async def test_refine_existing_freezes_one_exact_source_and_relation(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = await _generate_default_nine(factory)
    _validate(factory, source.actor, source.version_id)
    _open_gate(factory, source.actor, source.version_id)
    with factory() as session, session.begin():
        ArtifactService(session, source.actor).review(
            source.version_id,
            action="approve",
            comment="Approve source option set.",
            request_id="issue-127-approve-source",
        )

    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["intro.generate_options"]
    output["generation_mode"] = "refine_existing"
    output["source_intro_option_version_refs"] = [str(source.version_id)]
    output["options"] = [deepcopy(output["options"][0])]
    output["recommendation_summary"] = {
        "recommended_option_key": output["options"][0]["option_key"],
        "single_highest_score": True,
    }
    with factory() as session, session.begin():
        generate_id = IntroOptionRuntimeService(session, source.actor).stage_generation(
            project_id=source.project_id,
            lesson_unit_id=source.lesson_unit_id,
            generation_mode="refine_existing",
            source_artifact_version_id=source.version_id,
        )
    committed = await _execute(factory, source.actor, generate_id, output, "refine")

    with factory() as session:
        context = session.scalar(
            select(ContextSnapshot).where(ContextSnapshot.node_run_id == generate_id)
        )
        relation = session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.to_artifact_version_id == committed.artifact_version_id,
                ArtifactRelation.binding_key == "upstream.artifact.intro_option_set_source",
            )
        )
        assert context is not None and relation is not None
        bindings = {item["source"]: item["items"] for item in context.bindings_json["bindings"]}
        assert len(bindings["intro_options.existing_version"]) == 1
        assert bindings["intro_options.existing_version"][0]["source_version_id"] == str(
            source.version_id
        )
        assert relation.from_artifact_version_id == source.version_id
        assert relation.to_artifact_version_id == committed.artifact_version_id

    _validate(factory, source.actor, committed.artifact_version_id)
    _open_gate(factory, source.actor, committed.artifact_version_id)
    with factory() as session, session.begin():
        ArtifactService(session, source.actor).review(
            committed.artifact_version_id,
            action="approve",
            comment="Approve exact refined option.",
            request_id="issue-127-approve-refined",
        )


async def test_cross_tenant_source_is_rejected_before_provider_and_usage(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = await _generate_default_nine(factory)
    _validate(factory, source.actor, source.version_id)
    _open_gate(factory, source.actor, source.version_id)
    with factory() as session, session.begin():
        ArtifactService(session, source.actor).review(
            source.version_id,
            action="approve",
            comment="Approve tenant source.",
            request_id="issue-127-approve-tenant-source",
        )
        outsider_organization_id = new_uuid7()
        session.add(
            Organization(
                id=outsider_organization_id,
                slug=f"issue-127-{outsider_organization_id.hex[:12]}",
                name="Issue 127 outsider",
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        outsider = system_actor(outsider_organization_id)

    with factory() as session:
        with pytest.raises(ApiError):
            with session.begin():
                IntroOptionRuntimeService(session, outsider).stage_generation(
                    project_id=source.project_id,
                    lesson_unit_id=source.lesson_unit_id,
                    generation_mode="refine_existing",
                    source_artifact_version_id=source.version_id,
                )
        assert session.scalar(select(func.count()).select_from(GenerationAttempt)) == 1
        assert session.scalar(select(func.count()).select_from(UsageRecord)) == 1


async def test_quality_failure_rolls_back_report_terminal_and_event_atomically(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await _generate_default_nine(factory)
    with factory() as session, session.begin():
        validate_id = IntroOptionRuntimeService(session, prepared.actor).stage_quality(
            prepared.version_id
        )

    def fail_after_report(stage: str) -> None:
        if stage == "after_report":
            raise RuntimeError("intro quality transaction fault")

    with pytest.raises(RuntimeError, match="intro quality transaction fault"):
        ArtifactQualityService(
            SqlAlchemyArtifactQualityTransactionFactory(
                factory,
                prepared.actor,
                fault_injector=fail_after_report,
            ),
            intro_runtime_quality_validator_registry(),
        ).execute(validate_id)

    with factory() as session:
        validate = session.get(NodeRun, validate_id)
        assert validate is not None
        assert validate.status == "ready"
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactQualityReport)
                .where(ArtifactQualityReport.validate_node_run_id == validate_id)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(EventStreamEntry)
                .where(EventStreamEntry.resource_id == validate_id)
            )
            == 0
        )


async def _generate_default_nine(
    factory: sessionmaker[Session],
) -> PreparedIntroOption:
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    outputs = build_golden_branch_source_outputs(case)
    division = await _prepare_approval(factory, case, outputs["lesson.division.generate"])
    with factory() as session, session.begin():
        ArtifactService(session, division.actor).review(
            division.version_id,
            action="approve",
            comment="Approve the formal lesson division.",
            request_id="issue-127-approve-division",
        )
    with factory() as session:
        lesson = session.scalar(
            select(LessonUnit).where(
                LessonUnit.project_id == division.project_id,
                LessonUnit.lesson_key == "LESSON-001",
            )
        )
        assert lesson is not None
        lesson_unit_id = lesson.id
    with factory() as session, session.begin():
        generate_id = IntroOptionRuntimeService(session, division.actor).stage_generation(
            project_id=division.project_id,
            lesson_unit_id=lesson_unit_id,
            generation_mode="default_nine",
            source_artifact_version_id=None,
        )
    committed = await _execute(
        factory,
        division.actor,
        generate_id,
        outputs["intro.generate_options"],
        "default",
    )
    with factory() as session:
        version = session.get(ArtifactVersion, committed.artifact_version_id)
        assert version is not None
        return PreparedIntroOption(
            actor=division.actor,
            project_id=division.project_id,
            lesson_unit_id=lesson_unit_id,
            artifact_id=version.artifact_id,
            version_id=version.id,
            generate_node_id=generate_id,
        )


async def _execute(
    factory: sessionmaker[Session],
    actor: ActorContext,
    node_run_id: UUID,
    output: dict[str, object],
    suffix: str,
):
    return await NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, actor),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION: (
                    DeterministicNodeOutputProvider(output)
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    ).execute(node_run_id, request_id=f"issue-127-generate-{suffix}")


def _validate(
    factory: sessionmaker[Session],
    actor: ActorContext,
    version_id: UUID,
) -> tuple[UUID, UUID]:
    with factory() as session, session.begin():
        validate_id = IntroOptionRuntimeService(session, actor).stage_quality(version_id)
    result = ArtifactQualityService(
        SqlAlchemyArtifactQualityTransactionFactory(factory, actor),
        intro_runtime_quality_validator_registry(),
    ).execute(validate_id)
    assert result.conclusion == "passed"
    return validate_id, result.report_id


def _open_gate(
    factory: sessionmaker[Session],
    actor: ActorContext,
    version_id: UUID,
) -> UUID:
    with factory() as session, session.begin():
        return IntroOptionRuntimeService(session, actor).open_approval(version_id)
