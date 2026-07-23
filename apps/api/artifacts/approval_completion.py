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
from apps.api.workflows.approval_port import (
    ArtifactApprovalGateCommand,
    WorkflowApprovalReader,
    WorkflowArtifactApprovalPort,
)
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
    if output.approval_completion.kind == "workflow_gate":
        _complete_artifact_gate(
            session,
            actor,
            artifact,
            version,
            content_release_id=content_release_id,
            workflow_definition_version_id=workflow_definition_version_id,
            gate_node_key=output.quality_gate_node_key,
            branch_key=output.producer_branch_key,
            source_input_ref=output.approval_completion.source_input_ref,
            quality_source_binding=output.quality_source_binding,
        )
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


def retire_declared_approval_gate(
    session: Session,
    actor: ActorContext,
    artifact: Artifact,
    version: ArtifactVersion,
    *,
    fixed_release: tuple[UUID, UUID],
    review_completion: bool,
) -> None:
    if artifact.lesson_unit_id is None:
        return
    content_release_id, workflow_definition_version_id = fixed_release
    definition_key = ContentDefinitionApprovalReader(session).definition_key(
        definition_id=artifact.content_definition_version_id,
        content_release_id=content_release_id,
    )
    graph = WorkflowApprovalReader(session).published_graph(workflow_definition_version_id)
    if definition_key is None or graph is None:
        raise _invalid("The fixed content or workflow release is unavailable.")
    output = BUILTIN_WORKFLOW_REGISTRY.load(graph).output_definition_index.get(definition_key)
    if (
        output is None
        or output.approval_completion is None
        or output.approval_completion.kind != "workflow_gate"
    ):
        return
    command = _gate_command(
        artifact,
        version,
        content_release_id=content_release_id,
        workflow_definition_version_id=workflow_definition_version_id,
        gate_node_key=output.quality_gate_node_key,
        branch_key=output.producer_branch_key,
        source_input_ref=output.approval_completion.source_input_ref,
        quality_source_binding=output.quality_source_binding,
    )
    WorkflowArtifactApprovalPort(session, actor).retire_if_present(
        command,
        review_completion=review_completion,
    )


def _complete_artifact_gate(
    session: Session,
    actor: ActorContext,
    artifact: Artifact,
    version: ArtifactVersion,
    *,
    content_release_id: UUID,
    workflow_definition_version_id: UUID,
    gate_node_key: str | None,
    branch_key: str,
    source_input_ref: str | None,
    quality_source_binding: str | None,
) -> None:
    command = _gate_command(
        artifact,
        version,
        content_release_id=content_release_id,
        workflow_definition_version_id=workflow_definition_version_id,
        gate_node_key=gate_node_key,
        branch_key=branch_key,
        source_input_ref=source_input_ref,
        quality_source_binding=quality_source_binding,
    )
    WorkflowArtifactApprovalPort(session, actor).complete(command)


def _gate_command(
    artifact: Artifact,
    version: ArtifactVersion,
    *,
    content_release_id: UUID,
    workflow_definition_version_id: UUID,
    gate_node_key: str | None,
    branch_key: str,
    source_input_ref: str | None,
    quality_source_binding: str | None,
) -> ArtifactApprovalGateCommand:
    if artifact.lesson_unit_id is None or gate_node_key is None or source_input_ref is None:
        raise _invalid("The lesson-scoped approval gate declaration is incomplete.")
    source_type, source_version_id = _gate_source(version, quality_source_binding)
    return ArtifactApprovalGateCommand(
        project_id=artifact.project_id,
        lesson_unit_id=artifact.lesson_unit_id,
        source_type=source_type,
        source_version_id=source_version_id,
        content_release_id=content_release_id,
        workflow_definition_version_id=workflow_definition_version_id,
        gate_node_key=gate_node_key,
        branch_key=branch_key,
        source_input_ref=source_input_ref,
    )


def _gate_source(
    version: ArtifactVersion,
    quality_source_binding: str | None,
) -> tuple[str, UUID]:
    if quality_source_binding == "artifact":
        return "artifact", version.id
    if quality_source_binding == "linked_file_asset":
        value = version.content_json.get("file_asset_version_id")
        try:
            if type(value) is not str:
                raise ValueError("file version text is required")
            return "asset", UUID(value)
        except ValueError as exc:
            raise _invalid("The linked approval file identity is invalid.") from exc
    raise _invalid("The approval quality source binding is invalid.")


def _invalid(message: str) -> ApiError:
    return ApiError(
        status_code=409,
        code="LESSON_DIVISION_APPROVAL_INVALID",
        message=message,
    )
