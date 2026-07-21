"""Artifact-owned adapter for declared approval completion effects."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.lesson_division_port import ArtifactLessonDivisionReader
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.artifacts.quality_gate import ArtifactQualityApprovalGuard
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.content_runtime.approval_port import ContentDefinitionApprovalReader
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.lessons.approval_port import (
    LessonApprovalCompletionResult,
    LessonDivisionApprovalCommand,
    LessonDivisionApprovalPort,
)
from apps.api.workflows.approval_port import WorkflowApprovalReader
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY


def prepare_declared_approval(
    session: Session,
    actor: ActorContext,
    relations: ArtifactRelationService,
    artifact: Artifact,
    version: ArtifactVersion,
    *,
    previous_version_id: UUID | None,
    fixed_release: tuple[UUID, UUID],
    request_id: str | None,
) -> tuple[dict[str, str], list[UUID], list[UUID]]:
    content_release_id, workflow_definition_version_id = fixed_release
    quality_evidence = ArtifactQualityApprovalGuard(session, actor).require_evidence(
        artifact,
        version,
        content_release_id=content_release_id,
        workflow_definition_version_id=workflow_definition_version_id,
    )
    stale_ids, stale_node_ids = apply_declared_approval_effects(
        session,
        actor,
        relations,
        artifact,
        version,
        previous_version_id=previous_version_id,
        fixed_release=fixed_release,
        request_id=request_id,
    )
    return quality_evidence, stale_ids, stale_node_ids


def apply_declared_approval_effects(
    session: Session,
    actor: ActorContext,
    relations: ArtifactRelationService,
    artifact: Artifact,
    version: ArtifactVersion,
    *,
    previous_version_id: UUID | None,
    fixed_release: tuple[UUID, UUID],
    request_id: str | None,
) -> tuple[list[UUID], list[UUID]]:
    content_release_id, workflow_definition_version_id = fixed_release
    completion = _apply_declared_completion(
        session,
        actor,
        artifact,
        version,
        previous_version_id=previous_version_id,
        content_release_id=content_release_id,
        workflow_definition_version_id=workflow_definition_version_id,
        request_id=request_id,
    )
    return relations.propagate_stale(
        previous_version_id,
        version.id,
        selection=completion.stale_selection if completion is not None else None,
        carry_forward_selection=(completion.retained_selection if completion is not None else None),
    )


def _apply_declared_completion(
    session: Session,
    actor: ActorContext,
    artifact: Artifact,
    version: ArtifactVersion,
    *,
    previous_version_id: UUID | None,
    content_release_id: UUID,
    workflow_definition_version_id: UUID,
    request_id: str | None,
) -> LessonApprovalCompletionResult | None:
    definition_key = ContentDefinitionApprovalReader(session).definition_key(
        definition_id=artifact.content_definition_version_id,
        content_release_id=content_release_id,
    )
    graph = WorkflowApprovalReader(session).published_graph(workflow_definition_version_id)
    if definition_key is None or graph is None:
        raise _invalid("The fixed content or workflow release is unavailable.")
    output = BUILTIN_WORKFLOW_REGISTRY.load(graph).output_definition_index.get(definition_key)
    if output is None or output.approval_completion is None:
        return None
    if output.approval_completion.kind != "lesson_unit_sync":
        raise _invalid("The declared approval completion is unsupported.")
    if version.source_node_run_id is None or output.quality_gate_node_key is None:
        raise _invalid("The lesson approval completion lineage is incomplete.")
    previous = ArtifactLessonDivisionReader(session, actor).previous_content(previous_version_id)
    return LessonDivisionApprovalPort(session, actor).apply(
        LessonDivisionApprovalCommand(
            project_id=artifact.project_id,
            artifact_version_id=version.id,
            source_node_run_id=version.source_node_run_id,
            producer_node_key=output.producer_node_key,
            approval_gate_node_key=output.quality_gate_node_key,
            content_release_id=content_release_id,
            workflow_definition_version_id=workflow_definition_version_id,
            content=version.content_json,
            previous_content=previous,
            request_id=request_id,
        )
    )


def _invalid(message: str) -> ApiError:
    return ApiError(
        status_code=409,
        code="LESSON_DIVISION_APPROVAL_INVALID",
        message=message,
    )
