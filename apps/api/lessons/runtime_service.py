"""Application orchestration for the declared lesson-division three-node chain."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.lesson_division_port import (
    ArtifactLessonDivisionReader,
    GeneratedLessonDivisionFact,
)
from apps.api.assets.quality_port import SqlAlchemyAssetQualitySourcePort
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.prompt_runtime.lesson_context_port import LessonContextSnapshotReader
from apps.api.workflows.lesson_division_port import (
    LessonDivisionInputSnapshot,
    LessonDivisionRunNodes,
    LessonDivisionWorkflowPort,
)


class LessonDivisionRuntimeService:
    """Compose existing NodeRun, quality-report, and approval state machines."""

    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._artifacts = ArtifactLessonDivisionReader(session, actor)
        self._workflow = LessonDivisionWorkflowPort(session, actor)

    def initialize(self, project_id: UUID) -> LessonDivisionRunNodes:
        return self._workflow.initialize(project_id)

    def initialize_revision(self, project_id: UUID) -> LessonDivisionRunNodes:
        return self._workflow.initialize(project_id, revision=True)

    def stage_quality(self, artifact_version_id: UUID) -> UUID:
        fact = self._artifacts.require_generated(artifact_version_id)
        output = self._workflow.output_binding(
            fact.workflow_definition_version_id,
            fact.content_definition_key,
        )
        if output.quality_validate_node_key is None:
            raise _invalid("The fixed lesson-division validate node is missing.")
        run_id = self._workflow.require_source_run(
            source_node_run_id=fact.source_node_run_id,
            artifact_version_id=fact.artifact_version_id,
            expected_producer_node_key=output.producer_node_key,
            project_id=fact.project_id,
            content_release_id=fact.content_release_id,
            workflow_definition_version_id=fact.workflow_definition_version_id,
        )
        return self._workflow.stage_quality(
            run_id,
            output.quality_validate_node_key,
            source=LessonDivisionInputSnapshot(
                input_key="artifact:lesson_division",
                source_type="artifact",
                source_id=fact.artifact_id,
                source_version_id=fact.artifact_version_id,
                content_hash=fact.content_hash,
                content=fact.content,
            ),
            supporting=self._frozen_supporting_inputs(fact),
        )

    def _frozen_supporting_inputs(
        self,
        fact: GeneratedLessonDivisionFact,
    ) -> tuple[LessonDivisionInputSnapshot, ...]:
        reader = LessonContextSnapshotReader(
            self._session,
            self._actor.organization_id,
        )
        material_identity = reader.material_evidence(fact.context_snapshot_id)
        scope_identity = reader.approved_material_scope(fact.context_snapshot_id)
        if (
            material_identity.project_id != fact.project_id
            or material_identity.node_run_id != fact.source_node_run_id
            or scope_identity.project_id != fact.project_id
            or scope_identity.node_run_id != fact.source_node_run_id
        ):
            raise _invalid("The frozen material context is outside the generated output scope.")
        material = SqlAlchemyAssetQualitySourcePort(
            self._session,
            self._actor,
        ).load_supporting(
            fact.project_id,
            contract_ref="content:material_evidence",
            source_id=material_identity.source_material_id,
            source_version_id=material_identity.material_parse_version_id,
        )
        scope = self._artifacts.require_approved_material_scope(
            project_id=fact.project_id,
            artifact_version_id=scope_identity.artifact_version_id,
        )
        return (
            LessonDivisionInputSnapshot(
                input_key="approval:material_scope",
                source_type="artifact",
                source_id=scope.source_id,
                source_version_id=scope.source_version_id,
                content_hash=scope.content_hash,
                content=dict(scope.content),
            ),
            LessonDivisionInputSnapshot(
                input_key="content:material_evidence",
                source_type="material_parse",
                source_id=material.source_id,
                source_version_id=material.source_version_id,
                content_hash=material.content_hash,
                content=dict(material.content),
            ),
        )

    def open_approval(self, artifact_version_id: UUID) -> UUID:
        fact = self._artifacts.require_generated(artifact_version_id)
        output = self._workflow.output_binding(
            fact.workflow_definition_version_id,
            fact.content_definition_key,
        )
        if output.quality_gate_node_key is None:
            raise _invalid("The fixed lesson-division approval gate is missing.")
        run_id = self._workflow.require_source_run(
            source_node_run_id=fact.source_node_run_id,
            artifact_version_id=fact.artifact_version_id,
            expected_producer_node_key=output.producer_node_key,
            project_id=fact.project_id,
            content_release_id=fact.content_release_id,
            workflow_definition_version_id=fact.workflow_definition_version_id,
        )
        self._artifacts.require_quality_evidence(artifact_version_id)
        return self._workflow.open_gate(run_id, output.quality_gate_node_key)


def _invalid(message: str) -> ApiError:
    return ApiError(
        status_code=409,
        code="LESSON_DIVISION_RUNTIME_INVALID",
        message=message,
    )
