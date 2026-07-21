"""Workflow-owned state adapter for generic node execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.lessons.execution_port import LessonExecutionFacts, SqlAlchemyLessonExecutionPort
from apps.api.runtime_boundary.ports import WorkflowExecutionContext
from apps.api.workflows.execution_lease import SqlAlchemyNodeExecutionLeasePort
from apps.api.workflows.models import (
    BranchRun,
    NodeInputSnapshot,
    NodeRun,
    WorkflowDefinitionVersion,
    WorkflowRun,
)
from apps.api.workflows.repository import WorkflowRuntimeRepository
from apps.api.workflows.service import WorkflowRuntimeError, WorkflowRuntimeService
from workflow.definition import WorkflowNodeDefinition
from workflow.node_state import NodeStatus
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

_EXECUTION_INPUT_KEY = "runtime.execution"


class WorkflowExecutionPortError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SqlAlchemyWorkflowExecutionPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = WorkflowRuntimeRepository(session, actor)
        self._execution_leases = SqlAlchemyNodeExecutionLeasePort(session, self._repository)

    def require_context(
        self,
        node_run_id: UUID,
        *,
        for_update: bool,
    ) -> WorkflowExecutionContext:
        node, run = self._require_node_and_run(node_run_id, for_update=for_update)
        ProjectAccessService(self._session, self._actor).require(
            run.project_id,
            ProjectAction.GENERATE,
            for_update=for_update,
        )
        definition = self._published_node(run.workflow_definition_version_id, node.node_key)
        branch_key, lesson_key, lesson_unit_id = self._scope_facts(node, run, definition)
        return WorkflowExecutionContext(
            organization_id=node.organization_id,
            project_id=run.project_id,
            workflow_run_id=run.id,
            node_run_id=node.id,
            content_release_id=run.content_release_id,
            workflow_definition_version_id=run.workflow_definition_version_id,
            node_key=node.node_key,
            branch_key=branch_key,
            lesson_key=lesson_key,
            lesson_unit_id=lesson_unit_id,
            status=node.status,
        )

    def _require_node_and_run(
        self,
        node_run_id: UUID,
        *,
        for_update: bool,
    ) -> tuple[NodeRun, WorkflowRun]:
        node = self._repository.get_node(node_run_id, for_update=for_update)
        if node is None:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_NOT_FOUND",
                "the node run was not found",
            )
        run = self._repository.get_run(node.workflow_run_id, for_update=for_update)
        if run is None:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_NOT_FOUND",
                "the workflow run was not found",
            )
        return node, run

    def _published_node(
        self,
        version_id: UUID,
        node_key: str,
    ) -> WorkflowNodeDefinition:
        graph = self.published_graph(version_id)
        try:
            registered = BUILTIN_WORKFLOW_REGISTRY.load(dict(graph))
            registered.require_output_projection()
        except Exception as exc:
            raise WorkflowExecutionPortError(
                getattr(exc, "code", "WORKFLOW_RELEASE_UNSUPPORTED"),
                str(exc),
            ) from exc
        definition = registered.node_by_key.get(node_key)
        if definition is None:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_NODE_UNDECLARED",
                "the node run key is not declared by the fixed workflow",
            )
        return definition

    def _scope_facts(
        self,
        node: NodeRun,
        run: WorkflowRun,
        definition: WorkflowNodeDefinition,
    ) -> tuple[str, str | None, UUID | None]:
        if definition.execution_scope == "project":
            if node.branch_run_id is not None:
                raise WorkflowExecutionPortError(
                    "NODE_EXECUTION_SCOPE_MISMATCH",
                    "a project node cannot be bound to a lesson branch",
                )
            if definition.branch_key is None:
                raise WorkflowExecutionPortError(
                    "NODE_EXECUTION_BRANCH_MISSING",
                    "the published project node has no fixed branch",
                )
            return definition.branch_key, None, None
        if definition.execution_scope != "lesson_unit":
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_SCOPE_UNSUPPORTED",
                "the published node execution scope is unsupported",
            )
        branch_key, lesson = self._lesson_branch(node, run)
        if branch_key != definition.branch_key:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_BRANCH_MISMATCH",
                "the lesson branch does not match the published node binding",
            )
        return branch_key, lesson.lesson_key, lesson.lesson_unit_id

    def published_graph(self, workflow_definition_version_id: UUID) -> Mapping[str, Any]:
        workflow = self._session.get(WorkflowDefinitionVersion, workflow_definition_version_id)
        if workflow is None or workflow.status != "published":
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_WORKFLOW_UNPUBLISHED",
                "the fixed workflow definition is not published",
            )
        return cast(Mapping[str, Any], workflow.graph_json)

    def transition(self, node_run_id: UUID, target: NodeStatus) -> None:
        try:
            WorkflowRuntimeService(self._session, self._actor).transition_node(
                node_run_id,
                target,
            )
        except WorkflowRuntimeError as exc:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_STATE_CONFLICT",
                str(exc),
            ) from exc

    def freeze_execution(
        self,
        execution: WorkflowExecutionContext,
        *,
        request_id: str,
        snapshot: Mapping[str, Any],
    ) -> bool:
        payload = _plain_json(snapshot)
        payload["request_id"] = request_id
        content_hash = _content_hash(payload)
        existing = self._session.scalar(
            select(NodeInputSnapshot).where(
                NodeInputSnapshot.node_run_id == execution.node_run_id,
                NodeInputSnapshot.input_key == _EXECUTION_INPUT_KEY,
            )
        )
        if existing is not None:
            if existing.content_hash == content_hash and existing.snapshot_json == payload:
                return False
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_IDEMPOTENCY_CONFLICT",
                "the node run is already frozen for another execution request",
            )
        self._session.add(
            NodeInputSnapshot(
                id=new_uuid7(),
                node_run_id=execution.node_run_id,
                input_key=_EXECUTION_INPUT_KEY,
                source_type="workflow_definition",
                source_id=execution.workflow_run_id,
                source_version_id=execution.workflow_definition_version_id,
                content_hash=content_hash,
                snapshot_json=payload,
                created_by=self._actor.principal_id,
            )
        )
        self._session.flush()
        return True

    def claim_execution_owner(self, node_run_id: UUID, owner_token: str) -> None:
        self._execution_leases.claim(node_run_id, owner_token)

    def owns_execution_owner(self, node_run_id: UUID, owner_token: str) -> bool:
        return self._execution_leases.owns(node_run_id, owner_token)

    def release_execution_owner(self, node_run_id: UUID, owner_token: str) -> None:
        self._execution_leases.release(node_run_id, owner_token)

    def require_execution_request(self, node_run_id: UUID, request_id: str) -> None:
        existing = self._session.scalar(
            select(NodeInputSnapshot).where(
                NodeInputSnapshot.node_run_id == node_run_id,
                NodeInputSnapshot.input_key == _EXECUTION_INPUT_KEY,
            )
        )
        if existing is None or existing.snapshot_json.get("request_id") != request_id:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_IDEMPOTENCY_CONFLICT",
                "the node run is frozen for another execution request",
            )

    def frozen_execution_snapshot(self, node_run_id: UUID, request_id: str) -> dict[str, Any]:
        payload = self.find_frozen_execution_snapshot(node_run_id, request_id)
        if payload is None:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_IDEMPOTENCY_CONFLICT",
                "the node run is not frozen for this execution request",
            )
        return payload

    def find_frozen_execution_snapshot(
        self,
        node_run_id: UUID,
        request_id: str,
    ) -> dict[str, Any] | None:
        existing = self._session.scalar(
            select(NodeInputSnapshot).where(
                NodeInputSnapshot.node_run_id == node_run_id,
                NodeInputSnapshot.input_key == _EXECUTION_INPUT_KEY,
            )
        )
        if existing is None:
            return None
        if existing.snapshot_json.get("request_id") != request_id:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_IDEMPOTENCY_CONFLICT",
                "the node run is not frozen for this execution request",
            )
        payload = _plain_json(existing.snapshot_json)
        if existing.content_hash != _content_hash(payload):
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_FROZEN_INPUT_INVALID",
                "the frozen execution snapshot integrity check failed",
            )
        return payload

    def start(self, node_run_id: UUID) -> None:
        node = self._repository.get_node(node_run_id, for_update=True)
        if node is None:
            raise WorkflowExecutionPortError("NODE_EXECUTION_NOT_FOUND", "node run not found")
        status = NodeStatus(node.status)
        if status is NodeStatus.RUNNING:
            return
        if status is NodeStatus.CANCEL_REQUESTED:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_CANCEL_REQUESTED",
                "the node run was cancelled before invocation",
            )
        if status is NodeStatus.FAILED:
            self.transition(node_run_id, NodeStatus.QUEUED)
            status = NodeStatus.QUEUED
        elif status is NodeStatus.STALE:
            self.transition(node_run_id, NodeStatus.READY)
            status = NodeStatus.READY
        if status is NodeStatus.DRAFT:
            self.transition(node_run_id, NodeStatus.QUEUED)
            status = NodeStatus.QUEUED
        if status in {NodeStatus.READY, NodeStatus.QUEUED}:
            self.transition(node_run_id, NodeStatus.RUNNING)
            return
        raise WorkflowExecutionPortError(
            "NODE_EXECUTION_STATE_CONFLICT",
            f"node execution cannot start from {status.value}",
        )

    def complete(self, node_run_id: UUID, artifact_version_id: UUID) -> None:
        node = self._repository.get_node(node_run_id, for_update=True)
        if node is None:
            raise WorkflowExecutionPortError("NODE_EXECUTION_NOT_FOUND", "node run not found")
        if node.active_artifact_version_id is not None:
            if node.active_artifact_version_id == artifact_version_id:
                return
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_RESULT_CONFLICT",
                "the node run already points to another artifact version",
            )
        if NodeStatus(node.status) is NodeStatus.CANCEL_REQUESTED:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_CANCEL_REQUESTED",
                "the node run was cancelled before result commit",
            )
        self.transition(node_run_id, NodeStatus.REVIEW_REQUIRED)
        node.active_artifact_version_id = artifact_version_id
        node.finished_at = utc_now()
        node.last_error_code = None
        self._session.flush()

    def terminalize(self, node_run_id: UUID, *, code: str, cancelled: bool) -> None:
        node = self._repository.get_node(node_run_id, for_update=True)
        if node is None:
            return
        status = NodeStatus(node.status)
        if status in {NodeStatus.REVIEW_REQUIRED, NodeStatus.APPROVED, NodeStatus.CANCELLED}:
            return
        if cancelled:
            if status is NodeStatus.RUNNING:
                self.transition(node_run_id, NodeStatus.CANCEL_REQUESTED)
                status = NodeStatus.CANCEL_REQUESTED
            if status is NodeStatus.CANCEL_REQUESTED:
                self.transition(node_run_id, NodeStatus.CANCELLED)
            else:
                raise WorkflowExecutionPortError(
                    "NODE_EXECUTION_STATE_CONFLICT",
                    "the node run cannot be cancelled from its current state",
                )
        else:
            if status is NodeStatus.QUEUED:
                self.transition(node_run_id, NodeStatus.FAILED)
            elif status is NodeStatus.RUNNING or status is NodeStatus.CANCEL_REQUESTED:
                self.transition(node_run_id, NodeStatus.FAILED)
            else:
                raise WorkflowExecutionPortError(
                    "NODE_EXECUTION_STATE_CONFLICT",
                    "the node run cannot fail from its current state",
                )
        node.last_error_code = code[:160]
        node.finished_at = utc_now()
        self._session.flush()

    def committed_artifact(self, node_run_id: UUID) -> UUID | None:
        node = self._repository.get_node(node_run_id, for_update=True)
        if node is None:
            raise WorkflowExecutionPortError("NODE_EXECUTION_NOT_FOUND", "node run not found")
        return node.active_artifact_version_id

    def _lesson_branch(self, node: NodeRun, run: WorkflowRun) -> tuple[str, LessonExecutionFacts]:
        if node.branch_run_id is None:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_SCOPE_MISMATCH",
                "a lesson node requires a fixed branch run",
            )
        branch = self._session.scalar(
            select(BranchRun).where(
                BranchRun.id == node.branch_run_id,
                BranchRun.workflow_run_id == run.id,
                BranchRun.deleted_at.is_(None),
            )
        )
        if branch is None:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_BRANCH_NOT_FOUND",
                "the lesson branch is not visible or active",
            )
        try:
            lesson = SqlAlchemyLessonExecutionPort(self._session, self._actor).require_active(
                branch.lesson_unit_id,
                project_id=run.project_id,
            )
        except ValueError as exc:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_BRANCH_NOT_FOUND",
                str(exc),
            ) from exc
        return branch.branch_key, lesson


def _plain_json(value: Mapping[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(value, sort_keys=True, allow_nan=False)))


def _content_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
