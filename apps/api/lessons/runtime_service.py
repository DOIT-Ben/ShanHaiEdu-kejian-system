"""Application orchestration for the declared lesson-division three-node chain."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.artifacts.quality_gate import ArtifactQualityApprovalGuard
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.assets.quality_port import SqlAlchemyAssetQualitySourcePort
from apps.api.content_runtime.approval_port import ContentDefinitionApprovalReader
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.prompt_runtime.models import ContextSnapshot
from apps.api.workflows.approval_port import WorkflowApprovalReader
from apps.api.workflows.models import NodeRun, WorkflowRun
from apps.api.workflows.repository import WorkflowRuntimeRepository
from apps.api.workflows.service import WorkflowRuntimeService
from workflow.definition import WorkflowOutputDefinitionBinding
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY


@dataclass(frozen=True, slots=True)
class LessonDivisionRunNodes:
    workflow_run_id: UUID
    generate_node_run_id: UUID
    validate_node_run_id: UUID
    approve_node_run_id: UUID


class LessonDivisionRuntimeService:
    """Compose existing NodeRun, quality-report, and approval state machines."""

    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._workflow_repository = WorkflowRuntimeRepository(session, actor)

    def initialize(self, project_id: UUID) -> LessonDivisionRunNodes:
        project = ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.GENERATE,
            for_update=True,
        )
        run = self._workflow_repository.active_for_project(project.id, for_update=True)
        if run is None:
            run = WorkflowRuntimeService(self._session, self._actor).start_project_run(project.id)
        output = self._declared_lesson_output(
            workflow_definition_version_id=run.workflow_definition_version_id,
        )
        if output.quality_validate_node_key is None or output.quality_gate_node_key is None:
            raise self._invalid("The fixed lesson-division quality chain is incomplete.")
        generate = self._ensure_project_node(run, output.producer_node_key, NodeStatus.READY)
        validate = self._ensure_project_node(
            run,
            output.quality_validate_node_key,
            NodeStatus.NOT_READY,
        )
        approve = self._ensure_project_node(
            run,
            output.quality_gate_node_key,
            NodeStatus.NOT_READY,
        )
        return LessonDivisionRunNodes(run.id, generate.id, validate.id, approve.id)

    def stage_quality(self, artifact_version_id: UUID) -> UUID:
        version, artifact, run, output = self._require_generated_division(artifact_version_id)
        if output.quality_validate_node_key is None:
            raise self._invalid("The fixed lesson-division validate node is missing.")
        validate = self._require_project_node(run.id, output.quality_validate_node_key)
        source = self._material_evidence_source(version)
        workflow = WorkflowRuntimeService(self._session, self._actor)
        workflow.add_input_snapshot(
            validate.id,
            input_key="artifact:lesson_division",
            source_type="artifact",
            source_id=artifact.id,
            source_version_id=version.id,
            content_hash=version.content_hash,
            snapshot=version.content_json,
        )
        workflow.add_input_snapshot(
            validate.id,
            input_key="content:material_evidence",
            source_type="material_parse",
            source_id=source.source_id,
            source_version_id=source.source_version_id,
            content_hash=source.content_hash,
            snapshot=dict(source.content),
        )
        if NodeStatus(validate.status) is NodeStatus.NOT_READY:
            workflow.transition_node(validate.id, NodeStatus.READY)
        elif NodeStatus(validate.status) is not NodeStatus.READY:
            raise self._invalid("The lesson-division validate node cannot accept new inputs.")
        return validate.id

    def open_approval(self, artifact_version_id: UUID) -> UUID:
        version, artifact, run, output = self._require_generated_division(artifact_version_id)
        if output.quality_gate_node_key is None:
            raise self._invalid("The fixed lesson-division approval gate is missing.")
        project = ProjectAccessService(self._session, self._actor).require(
            artifact.project_id,
            ProjectAction.REVIEW,
            for_update=True,
        )
        ArtifactQualityApprovalGuard(self._session, self._actor).require_evidence(
            artifact,
            version,
            content_release_id=project.content_release_id,
            workflow_definition_version_id=project.workflow_definition_version_id,
        )
        gate = self._require_project_node(run.id, output.quality_gate_node_key)
        runtime = WorkflowRuntimeService(self._session, self._actor)
        status = NodeStatus(gate.status)
        if status is NodeStatus.NOT_READY:
            runtime.transition_node(gate.id, NodeStatus.READY)
            runtime.transition_node(gate.id, NodeStatus.DRAFT)
            runtime.transition_node(gate.id, NodeStatus.REVIEW_REQUIRED)
        elif status is not NodeStatus.REVIEW_REQUIRED:
            raise self._invalid("The lesson-division approval gate is not reviewable.")
        return gate.id

    def _require_generated_division(
        self,
        artifact_version_id: UUID,
    ) -> tuple[ArtifactVersion, Artifact, WorkflowRun, WorkflowOutputDefinitionBinding]:
        record = ArtifactRepository(self._session, self._actor).get_version(artifact_version_id)
        if record is None:
            raise self._not_found()
        version, artifact = record
        project = ProjectAccessService(self._session, self._actor).require(
            artifact.project_id,
            ProjectAction.GENERATE,
        )
        definition_key = ContentDefinitionApprovalReader(self._session).definition_key(
            definition_id=artifact.content_definition_version_id,
            content_release_id=project.content_release_id,
        )
        if definition_key is None:
            raise self._invalid("The generated artifact is outside the fixed content release.")
        output = self._declared_lesson_output(
            content_definition_key=definition_key,
            workflow_definition_version_id=project.workflow_definition_version_id,
        )
        if version.source_node_run_id is None:
            raise self._invalid("The lesson division has no generated source node.")
        source_node = self._session.get(NodeRun, version.source_node_run_id)
        run = (
            self._workflow_repository.get_run(source_node.workflow_run_id)
            if source_node is not None
            else None
        )
        if (
            source_node is None
            or run is None
            or source_node.organization_id != self._actor.organization_id
            or source_node.node_key != output.producer_node_key
            or source_node.active_artifact_version_id != version.id
            or run.project_id != artifact.project_id
            or run.content_release_id != project.content_release_id
            or run.workflow_definition_version_id != project.workflow_definition_version_id
        ):
            raise self._invalid("The artifact does not match the fixed lesson-division run.")
        return version, artifact, run, output

    def _declared_lesson_output(
        self,
        *,
        workflow_definition_version_id: UUID,
        content_definition_key: str | None = None,
    ) -> WorkflowOutputDefinitionBinding:
        graph = WorkflowApprovalReader(self._session).published_graph(
            workflow_definition_version_id
        )
        if graph is None:
            raise self._invalid("The fixed workflow definition is unavailable.")
        registered = BUILTIN_WORKFLOW_REGISTRY.load(graph)
        candidates = (
            (registered.output_definition_index.get(content_definition_key),)
            if content_definition_key is not None
            else tuple(registered.output_definition_index.values())
        )
        declared = tuple(
            output
            for output in candidates
            if output is not None
            and output.approval_completion is not None
            and output.approval_completion.kind == "lesson_unit_sync"
        )
        output = declared[0] if len(declared) == 1 else None
        if (
            output is None
            or output.approval_completion is None
            or output.approval_completion.kind != "lesson_unit_sync"
        ):
            raise self._invalid("The content output has no lesson-unit completion declaration.")
        return output

    def _material_evidence_source(self, version: ArtifactVersion):
        if version.context_snapshot_id is None:
            raise self._invalid("The generated lesson division has no frozen context.")
        context = self._session.get(ContextSnapshot, version.context_snapshot_id)
        if context is None or context.organization_id != self._actor.organization_id:
            raise self._invalid("The frozen lesson-division context is unavailable.")
        bindings = context.bindings_json.get("bindings")
        if not isinstance(bindings, Sequence):
            raise self._invalid("The frozen lesson-division context is invalid.")
        items: list[Mapping[str, Any]] = []
        for raw in cast(Sequence[object], bindings):
            if not isinstance(raw, Mapping):
                continue
            binding = cast(Mapping[str, Any], raw)
            if binding.get("source") != "material.approved_parse":
                continue
            raw_items = binding.get("items")
            if isinstance(raw_items, Sequence):
                items.extend(
                    cast(Mapping[str, Any], item)
                    for item in cast(Sequence[object], raw_items)
                    if isinstance(item, Mapping)
                )
        if len(items) != 1:
            raise self._invalid("Exactly one formal material evidence snapshot is required.")
        source_id = _uuid_value(items[0].get("source_id"))
        source_version_id = _uuid_value(items[0].get("source_version_id"))
        return SqlAlchemyAssetQualitySourcePort(self._session, self._actor).load_supporting(
            context.project_id,
            contract_ref="content:material_evidence",
            source_id=source_id,
            source_version_id=source_version_id,
        )

    def _ensure_project_node(
        self,
        run: WorkflowRun,
        node_key: str,
        status: NodeStatus,
    ) -> NodeRun:
        existing = self._session.scalar(
            select(NodeRun)
            .where(
                NodeRun.workflow_run_id == run.id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.branch_run_id.is_(None),
                NodeRun.node_key == node_key,
                NodeRun.deleted_at.is_(None),
            )
            .order_by(NodeRun.run_no.desc())
            .limit(1)
        )
        if existing is not None:
            return existing
        return WorkflowRuntimeService(self._session, self._actor).create_project_node_run(
            run.id,
            node_key=node_key,
            status=status,
        )

    def _require_project_node(self, run_id: UUID, node_key: str) -> NodeRun:
        node = self._session.scalar(
            select(NodeRun)
            .where(
                NodeRun.workflow_run_id == run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.branch_run_id.is_(None),
                NodeRun.node_key == node_key,
                NodeRun.deleted_at.is_(None),
            )
            .order_by(NodeRun.run_no.desc())
            .limit(1)
            .with_for_update(of=NodeRun)
        )
        if node is None:
            raise self._invalid("The fixed lesson-division node run is missing.")
        return node

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(status_code=404, code="ARTIFACT_NOT_FOUND", message="Not found.")

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(
            status_code=409,
            code="LESSON_DIVISION_RUNTIME_INVALID",
            message=message,
        )


def _uuid_value(value: object) -> UUID:
    if not isinstance(value, str):
        raise ApiError(
            status_code=409,
            code="LESSON_DIVISION_RUNTIME_INVALID",
            message="The frozen material identity is invalid.",
        )
    try:
        return UUID(value)
    except ValueError as exc:
        raise ApiError(
            status_code=409,
            code="LESSON_DIVISION_RUNTIME_INVALID",
            message="The frozen material identity is invalid.",
        ) from exc
