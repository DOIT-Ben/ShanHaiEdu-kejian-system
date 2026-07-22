"""Application orchestration for intro option generation, quality, and approval."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.intro_option_port import (
    ARTIFACT_INPUT_REF,
    CONTENT_DEFINITION_KEY,
    SOURCE_INPUT_REF,
    IntroOptionArtifactReader,
    ReviewableIntroOptionFact,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.lessons.approval_port import LessonApprovalReader
from apps.api.workflows.artifact_port import ArtifactInputSnapshot, ArtifactWorkflowPort


class IntroOptionRuntimeService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._artifacts = IntroOptionArtifactReader(session, actor)
        self._workflow = ArtifactWorkflowPort(
            session,
            actor,
            error_code="INTRO_OPTION_RUNTIME_INVALID",
        )
        self._session = session
        self._actor = actor

    def stage_generation(
        self,
        *,
        project_id: UUID,
        lesson_unit_id: UUID,
        generation_mode: str,
        source_artifact_version_id: UUID | None,
    ) -> UUID:
        lesson = LessonApprovalReader(self._session, self._actor).current_lesson(
            project_id=project_id,
            lesson_unit_id=lesson_unit_id,
        )
        if lesson is None:
            raise self._invalid("The target lesson is not active and approved.")
        scope = self._workflow.require_lesson_scope(
            project_id=project_id,
            lesson_unit_id=lesson_unit_id,
            branch_key="intro_options",
        )
        output = self._workflow.output_binding(
            scope.workflow_definition_version_id,
            CONTENT_DEFINITION_KEY,
        )
        completion = output.approval_completion
        if (
            output.producer_node_key != "intro.generate_options"
            or completion is None
            or completion.kind != "workflow_gate"
            or completion.source_input_ref != ARTIFACT_INPUT_REF
        ):
            raise self._invalid("The fixed Intro workflow-gate completion is unavailable.")
        if generation_mode == "default_nine" and source_artifact_version_id is None:
            selected: dict[str, UUID] = {}
        elif generation_mode == "refine_existing" and source_artifact_version_id is not None:
            self._artifacts.require_exact_source(
                project_id=project_id,
                lesson_unit_id=lesson_unit_id,
                lesson_key=lesson.lesson_key,
                content_release_id=scope.content_release_id,
                version_id=source_artifact_version_id,
            )
            selected = {SOURCE_INPUT_REF: source_artifact_version_id}
        else:
            raise self._invalid("The generation mode and exact source cardinality disagree.")
        return self._workflow.stage_generation(
            scope,
            output.producer_node_key,
            selected_artifact_versions=selected,
        )

    def stage_quality(self, artifact_version_id: UUID) -> UUID:
        fact = self._artifacts.require_reviewable(artifact_version_id)
        output, scope = self._output_and_scope(fact)
        if output.quality_validate_node_key is None:
            raise self._invalid("The fixed Intro validate node is missing.")
        return self._workflow.stage_quality(
            scope,
            output.quality_validate_node_key,
            source=self._source_snapshot(fact),
            supporting=self._supporting_snapshots(fact),
        )

    def open_approval(self, artifact_version_id: UUID) -> UUID:
        fact = self._artifacts.require_reviewable(artifact_version_id)
        output, scope = self._output_and_scope(fact)
        if output.quality_gate_node_key is None or len(output.quality_report_refs) != 1:
            raise self._invalid("The fixed Intro approval gate is invalid.")
        evidence = self._artifacts.require_quality_evidence(artifact_version_id)
        report_id = _uuid_value(evidence.get("report_id"))
        evidence_hash = evidence.get("evidence_hash")
        if type(evidence_hash) is not str or len(evidence_hash) != 64:
            raise self._invalid("The exact Intro quality evidence is invalid.")
        return self._workflow.open_gate(
            scope,
            output.quality_gate_node_key,
            source=self._source_snapshot(fact),
            report=ArtifactInputSnapshot(
                input_key=output.quality_report_refs[0],
                source_type="quality_report",
                source_id=report_id,
                source_version_id=report_id,
                content_hash=evidence_hash,
                content=cast(dict[str, object], dict(evidence)),
            ),
        )

    def _output_and_scope(self, fact: ReviewableIntroOptionFact):
        output = self._workflow.output_binding(
            fact.workflow_definition_version_id,
            CONTENT_DEFINITION_KEY,
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

    @staticmethod
    def _supporting_snapshots(
        fact: ReviewableIntroOptionFact,
    ) -> tuple[ArtifactInputSnapshot, ...]:
        return (
            ArtifactInputSnapshot(
                input_key="approval:lesson_division",
                source_type="artifact",
                source_id=fact.division.source_id,
                source_version_id=fact.division.source_version_id,
                content_hash=fact.division.content_hash,
                content=cast(dict[str, object], dict(fact.division.content)),
            ),
            ArtifactInputSnapshot(
                input_key="content:material_evidence",
                source_type="material_parse",
                source_id=fact.material.source_id,
                source_version_id=fact.material.source_version_id,
                content_hash=fact.material.content_hash,
                content=cast(dict[str, object], dict(fact.material.content)),
            ),
        )

    @staticmethod
    def _source_snapshot(fact: ReviewableIntroOptionFact) -> ArtifactInputSnapshot:
        return ArtifactInputSnapshot(
            input_key=ARTIFACT_INPUT_REF,
            source_type="artifact",
            source_id=fact.artifact_id,
            source_version_id=fact.artifact_version_id,
            content_hash=fact.content_hash,
            content=cast(dict[str, object], dict(fact.content)),
        )

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=409, code="INTRO_OPTION_RUNTIME_INVALID", message=message)


def _uuid_value(value: object) -> UUID:
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ApiError(
            status_code=409,
            code="INTRO_OPTION_RUNTIME_INVALID",
            message="The exact Intro quality report is invalid.",
        ) from exc
