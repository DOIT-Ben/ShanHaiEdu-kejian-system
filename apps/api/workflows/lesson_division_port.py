"""Workflow-owned NodeRun application port for the lesson-division chain."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.workflows.models import (
    NodeInputSnapshot,
    NodeRun,
    WorkflowDefinitionVersion,
    WorkflowRun,
)
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


@dataclass(frozen=True, slots=True)
class LessonDivisionInputSnapshot:
    input_key: str
    source_type: str
    source_id: UUID
    source_version_id: UUID
    content_hash: str
    content: dict[str, object]


class LessonDivisionWorkflowPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = WorkflowRuntimeRepository(session, actor)

    def initialize(self, project_id: UUID, *, revision: bool = False) -> LessonDivisionRunNodes:
        project = ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.GENERATE,
            for_update=True,
        )
        run = self._repository.active_for_project(project.id, for_update=True)
        if run is None:
            if revision:
                raise self._invalid("The fixed workflow run is unavailable for revision.")
            run = WorkflowRuntimeService(self._session, self._actor).start_project_run(project.id)
        output = self.output_binding(run.workflow_definition_version_id)
        validate_key, gate_key = self._quality_keys(output)
        if revision:
            previous_gate = self._latest_project_node(run.id, gate_key, for_update=True)
            if previous_gate is None or NodeStatus(previous_gate.status) is not NodeStatus.APPROVED:
                raise self._invalid("The preceding lesson-division approval is not complete.")
            return self._create_chain(run, output.producer_node_key, validate_key, gate_key)
        generate = self._ensure_project_node(run, output.producer_node_key, NodeStatus.READY)
        validate = self._ensure_project_node(run, validate_key, NodeStatus.NOT_READY)
        approve = self._ensure_project_node(run, gate_key, NodeStatus.NOT_READY)
        return LessonDivisionRunNodes(run.id, generate.id, validate.id, approve.id)

    def output_binding(
        self,
        workflow_definition_version_id: UUID,
        content_definition_key: str | None = None,
    ) -> WorkflowOutputDefinitionBinding:
        workflow = self._session.get(
            WorkflowDefinitionVersion,
            workflow_definition_version_id,
        )
        if workflow is None or workflow.status != "published":
            raise self._invalid("The fixed workflow definition is unavailable.")
        registered = BUILTIN_WORKFLOW_REGISTRY.load(workflow.graph_json)
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
        if len(declared) != 1:
            raise self._invalid("The output has no unique lesson-unit completion declaration.")
        return declared[0]

    def require_source_run(
        self,
        *,
        source_node_run_id: UUID,
        artifact_version_id: UUID,
        expected_producer_node_key: str,
        project_id: UUID,
        content_release_id: UUID,
        workflow_definition_version_id: UUID,
    ) -> UUID:
        node = self._session.scalar(
            select(NodeRun)
            .where(
                NodeRun.id == source_node_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.node_key == expected_producer_node_key,
                NodeRun.branch_run_id.is_(None),
                NodeRun.deleted_at.is_(None),
            )
            .with_for_update(of=NodeRun)
        )
        run = self._repository.get_run(node.workflow_run_id) if node is not None else None
        if (
            node is None
            or run is None
            or node.active_artifact_version_id != artifact_version_id
            or run.project_id != project_id
            or run.content_release_id != content_release_id
            or run.workflow_definition_version_id != workflow_definition_version_id
        ):
            raise self._invalid("The generated output is outside the fixed workflow run.")
        return run.id

    def stage_quality(
        self,
        workflow_run_id: UUID,
        validate_node_key: str,
        *,
        source: LessonDivisionInputSnapshot,
        supporting: LessonDivisionInputSnapshot,
    ) -> UUID:
        validate = self._require_project_node(workflow_run_id, validate_node_key)
        runtime = WorkflowRuntimeService(self._session, self._actor)
        replayed = tuple(
            self._ensure_input_snapshot(validate.id, snapshot, runtime)
            for snapshot in (source, supporting)
        )
        inputs_replayed = all(replayed)
        if NodeStatus(validate.status) is NodeStatus.NOT_READY:
            runtime.transition_node(validate.id, NodeStatus.READY)
        elif NodeStatus(validate.status) is not NodeStatus.READY and not inputs_replayed:
            raise self._invalid("The validate node cannot accept new inputs.")
        return validate.id

    def _ensure_input_snapshot(
        self,
        node_run_id: UUID,
        expected: LessonDivisionInputSnapshot,
        runtime: WorkflowRuntimeService,
    ) -> bool:
        existing = self._session.scalar(
            select(NodeInputSnapshot)
            .where(
                NodeInputSnapshot.node_run_id == node_run_id,
                NodeInputSnapshot.input_key == expected.input_key,
            )
            .with_for_update(of=NodeInputSnapshot)
        )
        if existing is None:
            runtime.add_input_snapshot(
                node_run_id,
                input_key=expected.input_key,
                source_type=expected.source_type,
                source_id=expected.source_id,
                source_version_id=expected.source_version_id,
                content_hash=expected.content_hash,
                snapshot=expected.content,
            )
            return False
        if (
            existing.source_type != expected.source_type
            or existing.source_id != expected.source_id
            or existing.source_version_id != expected.source_version_id
            or existing.content_hash != expected.content_hash
            or existing.snapshot_json != expected.content
        ):
            raise self._invalid("The validate node already has different frozen inputs.")
        return True

    def open_gate(self, workflow_run_id: UUID, gate_node_key: str) -> UUID:
        gate = self._require_project_node(workflow_run_id, gate_node_key)
        runtime = WorkflowRuntimeService(self._session, self._actor)
        status = NodeStatus(gate.status)
        if status is NodeStatus.NOT_READY:
            runtime.transition_node(gate.id, NodeStatus.READY)
            runtime.transition_node(gate.id, NodeStatus.DRAFT)
            runtime.transition_node(gate.id, NodeStatus.REVIEW_REQUIRED)
        elif status is not NodeStatus.REVIEW_REQUIRED:
            raise self._invalid("The approval gate is not reviewable.")
        return gate.id

    def complete_gate(self, workflow_run_id: UUID, gate_node_key: str) -> None:
        gate = self._require_project_node(workflow_run_id, gate_node_key)
        if NodeStatus(gate.status) is not NodeStatus.REVIEW_REQUIRED:
            raise self._invalid("The exact approval gate is not awaiting review.")
        WorkflowRuntimeService(self._session, self._actor).transition_node(
            gate.id,
            NodeStatus.APPROVED,
        )

    def _create_chain(
        self,
        run: WorkflowRun,
        generate_key: str,
        validate_key: str,
        gate_key: str,
    ) -> LessonDivisionRunNodes:
        runtime = WorkflowRuntimeService(self._session, self._actor)
        generate = runtime.create_project_node_run(
            run.id, node_key=generate_key, status=NodeStatus.READY
        )
        validate = runtime.create_project_node_run(
            run.id, node_key=validate_key, status=NodeStatus.NOT_READY
        )
        gate = runtime.create_project_node_run(
            run.id, node_key=gate_key, status=NodeStatus.NOT_READY
        )
        return LessonDivisionRunNodes(run.id, generate.id, validate.id, gate.id)

    def _ensure_project_node(
        self,
        run: WorkflowRun,
        node_key: str,
        status: NodeStatus,
    ) -> NodeRun:
        existing = self._latest_project_node(run.id, node_key)
        if existing is not None:
            return existing
        return WorkflowRuntimeService(self._session, self._actor).create_project_node_run(
            run.id,
            node_key=node_key,
            status=status,
        )

    def _require_project_node(self, run_id: UUID, node_key: str) -> NodeRun:
        node = self._latest_project_node(run_id, node_key, for_update=True)
        if node is None:
            raise self._invalid("The fixed lesson-division NodeRun is missing.")
        return node

    def _latest_project_node(
        self,
        run_id: UUID,
        node_key: str,
        *,
        for_update: bool = False,
    ) -> NodeRun | None:
        statement = (
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
        )
        if for_update:
            statement = statement.with_for_update(of=NodeRun)
        return self._session.scalar(statement)

    @staticmethod
    def _quality_keys(output: WorkflowOutputDefinitionBinding) -> tuple[str, str]:
        if output.quality_validate_node_key is None or output.quality_gate_node_key is None:
            raise LessonDivisionWorkflowPort._invalid("The quality chain is incomplete.")
        return output.quality_validate_node_key, output.quality_gate_node_key

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(
            status_code=409,
            code="LESSON_DIVISION_RUNTIME_INVALID",
            message=message,
        )
