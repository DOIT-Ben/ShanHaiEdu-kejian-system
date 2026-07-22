"""Application orchestration for lesson-plan generation review and approval."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.lesson_plan_port import (
    ArtifactLessonPlanReader,
    ReviewableLessonPlanFact,
)
from apps.api.assets.quality_port import SqlAlchemyAssetQualitySourcePort
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.prompt_runtime.lesson_context_port import LessonContextSnapshotReader
from apps.api.workflows.lesson_plan_port import (
    LessonPlanInputSnapshot,
    LessonPlanRunScope,
    LessonPlanWorkflowPort,
)
from workflow.definition import WorkflowOutputDefinitionBinding


class LessonPlanRuntimeService:
    """Compose existing execution, quality, authoring, and approval state machines."""

    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._artifacts = ArtifactLessonPlanReader(session, actor)
        self._workflow = LessonPlanWorkflowPort(session, actor)

    def stage_quality(self, artifact_version_id: UUID) -> UUID:
        fact = self._artifacts.require_reviewable(artifact_version_id)
        output, scope = self._output_and_scope(fact)
        if output.quality_validate_node_key is None:
            raise self._invalid("The fixed lesson-plan validate node is missing.")
        return self._workflow.stage_quality(
            scope,
            output.quality_validate_node_key,
            source=self._source_snapshot(fact),
            supporting=self._supporting_snapshots(fact),
        )

    def open_approval(self, artifact_version_id: UUID) -> UUID:
        fact = self._artifacts.require_reviewable(artifact_version_id)
        output, scope = self._output_and_scope(fact)
        if output.quality_gate_node_key is None:
            raise self._invalid("The fixed lesson-plan approval gate is missing.")
        evidence = self._artifacts.require_quality_evidence(artifact_version_id)
        report_id = _uuid_value(evidence.get("report_id"))
        evidence_hash = evidence.get("evidence_hash")
        if type(evidence_hash) is not str or len(evidence_hash) != 64:
            raise self._invalid("The exact lesson-plan quality evidence is invalid.")
        return self._workflow.open_gate(
            scope,
            output.quality_gate_node_key,
            source=self._source_snapshot(fact),
            report=LessonPlanInputSnapshot(
                input_key="report:lesson_plan_quality",
                source_type="quality_report",
                source_id=report_id,
                source_version_id=report_id,
                content_hash=evidence_hash,
                content=cast(dict[str, object], dict(evidence)),
            ),
        )

    def _output_and_scope(
        self,
        fact: ReviewableLessonPlanFact,
    ) -> tuple[WorkflowOutputDefinitionBinding, LessonPlanRunScope]:
        output = self._workflow.output_binding(
            fact.workflow_definition_version_id,
            fact.content_definition_key,
        )
        scope = self._workflow.require_source_scope(
            source_node_run_id=fact.lineage_node_run_id,
            source_artifact_version_id=fact.lineage_artifact_version_id,
            expected_producer_node_key=output.producer_node_key,
            project_id=fact.project_id,
            lesson_unit_id=fact.lesson_unit_id,
            content_release_id=fact.content_release_id,
            workflow_definition_version_id=fact.workflow_definition_version_id,
        )
        return output, scope

    def _supporting_snapshots(
        self,
        fact: ReviewableLessonPlanFact,
    ) -> tuple[LessonPlanInputSnapshot, ...]:
        identity = LessonContextSnapshotReader(
            self._session,
            self._actor.organization_id,
        ).material_evidence(fact.division_context_snapshot_id)
        if identity.project_id != fact.project_id:
            raise self._invalid("The approved division material context is outside the project.")
        material = SqlAlchemyAssetQualitySourcePort(self._session, self._actor).load_supporting(
            fact.project_id,
            contract_ref="content:material_evidence",
            source_id=identity.source_material_id,
            source_version_id=identity.material_parse_version_id,
        )
        return (
            LessonPlanInputSnapshot(
                input_key="approval:lesson_division",
                source_type="artifact",
                source_id=fact.division.source_id,
                source_version_id=fact.division.source_version_id,
                content_hash=fact.division.content_hash,
                content=cast(dict[str, object], dict(fact.division.content)),
            ),
            LessonPlanInputSnapshot(
                input_key="content:material_evidence",
                source_type="material_parse",
                source_id=material.source_id,
                source_version_id=material.source_version_id,
                content_hash=material.content_hash,
                content=cast(dict[str, object], dict(material.content)),
            ),
        )

    @staticmethod
    def _source_snapshot(fact: ReviewableLessonPlanFact) -> LessonPlanInputSnapshot:
        return LessonPlanInputSnapshot(
            input_key="artifact:lesson_plan",
            source_type="artifact",
            source_id=fact.artifact_id,
            source_version_id=fact.artifact_version_id,
            content_hash=fact.content_hash,
            content=cast(dict[str, object], dict(fact.content)),
        )

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=409, code="LESSON_PLAN_RUNTIME_INVALID", message=message)


def _uuid_value(value: object) -> UUID:
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ApiError(
            status_code=409,
            code="LESSON_PLAN_RUNTIME_INVALID",
            message="The exact lesson-plan quality report is invalid.",
        ) from exc
