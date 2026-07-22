"""Workflow-owned NodeRun staging for one lesson-plan artifact version."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.workflows.models import (
    BranchRun,
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
class LessonPlanInputSnapshot:
    input_key: str
    source_type: str
    source_id: UUID
    source_version_id: UUID
    content_hash: str
    content: dict[str, object]


@dataclass(frozen=True, slots=True)
class LessonPlanRunScope:
    workflow_run_id: UUID
    branch_run_id: UUID


class LessonPlanWorkflowPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = WorkflowRuntimeRepository(session, actor)

    def output_binding(
        self,
        workflow_definition_version_id: UUID,
        content_definition_key: str,
    ) -> WorkflowOutputDefinitionBinding:
        workflow = self._session.get(WorkflowDefinitionVersion, workflow_definition_version_id)
        if workflow is None or workflow.status != "published":
            raise self._invalid("The fixed workflow definition is unavailable.")
        output = BUILTIN_WORKFLOW_REGISTRY.load(workflow.graph_json).output_definition_index.get(
            content_definition_key
        )
        if output is None or output.execution_scope != "lesson_unit":
            raise self._invalid("The lesson-plan output binding is unavailable.")
        return output

    def require_source_scope(
        self,
        *,
        source_node_run_id: UUID,
        source_artifact_version_id: UUID,
        expected_producer_node_key: str,
        project_id: UUID,
        lesson_unit_id: UUID,
        content_release_id: UUID,
        workflow_definition_version_id: UUID,
    ) -> LessonPlanRunScope:
        row = self._session.execute(
            select(NodeRun, BranchRun, WorkflowRun)
            .join(BranchRun, BranchRun.id == NodeRun.branch_run_id)
            .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
            .where(
                NodeRun.id == source_node_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.node_key == expected_producer_node_key,
                NodeRun.active_artifact_version_id == source_artifact_version_id,
                NodeRun.deleted_at.is_(None),
                BranchRun.lesson_unit_id == lesson_unit_id,
                BranchRun.status == "active",
                BranchRun.deleted_at.is_(None),
                WorkflowRun.project_id == project_id,
                WorkflowRun.content_release_id == content_release_id,
                WorkflowRun.workflow_definition_version_id == workflow_definition_version_id,
                WorkflowRun.status == "active",
            )
            .with_for_update(of=NodeRun)
        ).one_or_none()
        if row is None:
            raise self._invalid("The generated lesson plan is outside its fixed lesson branch.")
        _node, branch, run = row
        return LessonPlanRunScope(run.id, branch.id)

    def stage_quality(
        self,
        scope: LessonPlanRunScope,
        validate_node_key: str,
        *,
        source: LessonPlanInputSnapshot,
        supporting: tuple[LessonPlanInputSnapshot, ...],
    ) -> UUID:
        existing = self._node_for_source(
            scope.branch_run_id,
            validate_node_key,
            source,
        )
        runtime = WorkflowRuntimeService(self._session, self._actor)
        if existing is None:
            node = runtime.create_branch_node_run(
                scope.workflow_run_id,
                scope.branch_run_id,
                node_key=validate_node_key,
                status=NodeStatus.NOT_READY,
            )
        else:
            node = existing
        replayed = tuple(
            self._ensure_snapshot(node.id, snapshot, runtime) for snapshot in (source, *supporting)
        )
        if NodeStatus(node.status) is NodeStatus.NOT_READY:
            runtime.transition_node(node.id, NodeStatus.READY)
        elif not all(replayed):
            raise self._invalid("The validate node cannot accept different frozen inputs.")
        return node.id

    def open_gate(
        self,
        scope: LessonPlanRunScope,
        gate_node_key: str,
        *,
        source: LessonPlanInputSnapshot,
        report: LessonPlanInputSnapshot,
    ) -> UUID:
        existing = self._node_for_source(scope.branch_run_id, gate_node_key, source)
        runtime = WorkflowRuntimeService(self._session, self._actor)
        if existing is None:
            node = runtime.create_branch_node_run(
                scope.workflow_run_id,
                scope.branch_run_id,
                node_key=gate_node_key,
                status=NodeStatus.NOT_READY,
            )
        else:
            node = existing
        replayed = (
            self._ensure_snapshot(node.id, source, runtime),
            self._ensure_snapshot(node.id, report, runtime),
        )
        status = NodeStatus(node.status)
        if status is NodeStatus.NOT_READY:
            runtime.transition_node(node.id, NodeStatus.READY)
            runtime.transition_node(node.id, NodeStatus.DRAFT)
            runtime.transition_node(node.id, NodeStatus.REVIEW_REQUIRED)
        elif status is not NodeStatus.REVIEW_REQUIRED or not all(replayed):
            raise self._invalid("The approval gate cannot accept different frozen inputs.")
        return node.id

    def _node_for_source(
        self,
        branch_run_id: UUID,
        node_key: str,
        source: LessonPlanInputSnapshot,
    ) -> NodeRun | None:
        return self._session.scalar(
            select(NodeRun)
            .join(NodeInputSnapshot, NodeInputSnapshot.node_run_id == NodeRun.id)
            .where(
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.branch_run_id == branch_run_id,
                NodeRun.node_key == node_key,
                NodeRun.deleted_at.is_(None),
                NodeInputSnapshot.input_key == source.input_key,
                NodeInputSnapshot.source_version_id == source.source_version_id,
                NodeInputSnapshot.content_hash == source.content_hash,
            )
            .order_by(NodeRun.run_no.desc())
            .limit(1)
            .with_for_update(of=NodeRun)
        )

    def _ensure_snapshot(
        self,
        node_run_id: UUID,
        expected: LessonPlanInputSnapshot,
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
            raise self._invalid("The node already has different frozen inputs.")
        return True

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=409, code="LESSON_PLAN_RUNTIME_INVALID", message=message)
