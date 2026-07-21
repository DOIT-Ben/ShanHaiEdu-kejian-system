"""Workflow-owned application interface for deterministic quality validation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.identity.context import ActorContext
from apps.api.workflows.execution_port import (
    SqlAlchemyWorkflowExecutionPort,
    WorkflowExecutionPortError,
)
from apps.api.workflows.models import NodeInputSnapshot
from apps.api.workflows.repository import WorkflowRuntimeRepository
from workflow.node_state import NodeStatus


class SqlAlchemyQualityWorkflowPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._repository = WorkflowRuntimeRepository(session, actor)
        self._execution = SqlAlchemyWorkflowExecutionPort(session, actor)

    def require_artifact_input(self, node_run_id: UUID, input_key: str) -> tuple[UUID, str]:
        snapshot = self._session.scalar(
            select(NodeInputSnapshot).where(
                NodeInputSnapshot.node_run_id == node_run_id,
                NodeInputSnapshot.input_key == input_key,
            )
        )
        if (
            snapshot is None
            or snapshot.source_type != "artifact"
            or snapshot.source_version_id is None
        ):
            raise WorkflowExecutionPortError(
                "QUALITY_SOURCE_INPUT_MISSING",
                "the validate node has no exact artifact input snapshot",
            )
        return snapshot.source_version_id, snapshot.content_hash

    def complete(self, node_run_id: UUID, *, passed: bool) -> None:
        node = self._repository.get_node(node_run_id, for_update=True)
        if node is None or NodeStatus(node.status) is not NodeStatus.RUNNING:
            raise WorkflowExecutionPortError(
                "NODE_EXECUTION_STATE_CONFLICT",
                "the quality validate node is not running",
            )
        if passed:
            self._execution.transition(node_run_id, NodeStatus.REVIEW_REQUIRED)
            self._execution.transition(node_run_id, NodeStatus.APPROVED)
            node.last_error_code = None
        else:
            self._execution.transition(node_run_id, NodeStatus.FAILED)
            node.last_error_code = "QUALITY_VALIDATION_FAILED"
        node.finished_at = utc_now()
        self._session.flush()
