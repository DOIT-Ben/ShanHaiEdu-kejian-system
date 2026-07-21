"""Workflow-owned application interface for deterministic quality validation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.identity.context import ActorContext
from apps.api.workflows.execution_port import (
    SqlAlchemyWorkflowExecutionPort,
    WorkflowExecutionPortError,
)
from apps.api.workflows.models import NodeInputSnapshot, NodeRun
from apps.api.workflows.repository import WorkflowRuntimeRepository
from workflow.node_state import NodeStatus


@dataclass(frozen=True, slots=True)
class QualitySourceInput:
    source_type: str
    source_id: UUID
    source_version_id: UUID
    content_hash: str


@dataclass(frozen=True, slots=True)
class QualityFailureRouting:
    organization_id: UUID
    project_id: UUID
    content_release_id: UUID
    workflow_definition_version_id: UUID


class SqlAlchemyQualityWorkflowPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._repository = WorkflowRuntimeRepository(session, actor)
        self._execution = SqlAlchemyWorkflowExecutionPort(session, actor)

    def require_source_input(self, node_run_id: UUID, input_key: str) -> QualitySourceInput:
        snapshot = self._session.scalar(
            select(NodeInputSnapshot).where(
                NodeInputSnapshot.node_run_id == node_run_id,
                NodeInputSnapshot.input_key == input_key,
            )
        )
        if (
            snapshot is None
            or snapshot.source_type not in {"artifact", "asset"}
            or snapshot.source_version_id is None
        ):
            raise WorkflowExecutionPortError(
                "QUALITY_SOURCE_INPUT_MISSING",
                "the validate node has no exact quality source input snapshot",
            )
        return QualitySourceInput(
            source_type=snapshot.source_type,
            source_id=snapshot.source_id,
            source_version_id=snapshot.source_version_id,
            content_hash=snapshot.content_hash,
        )

    def fail_prepare(self, node_run_id: UUID, *, code: str) -> QualityFailureRouting | None:
        node = self._repository.get_node(node_run_id, for_update=True)
        if node is None:
            return None
        run = self._repository.get_run(node.workflow_run_id)
        if run is None:
            return None
        if NodeStatus(node.status) is NodeStatus.FAILED and node.last_error_code == code:
            return None
        self._execution.start(node_run_id)
        self._execution.terminalize(node_run_id, code=code, cancelled=False)
        return QualityFailureRouting(
            organization_id=node.organization_id,
            project_id=run.project_id,
            content_release_id=run.content_release_id,
            workflow_definition_version_id=run.workflow_definition_version_id,
        )

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


class QualityNodeRoutingReader:
    """Resolve only the tenant needed to construct a scoped worker actor."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def organization_id(self, node_run_id: UUID) -> UUID | None:
        return self._session.scalar(
            select(NodeRun.organization_id).where(
                NodeRun.id == node_run_id,
                NodeRun.deleted_at.is_(None),
            )
        )
