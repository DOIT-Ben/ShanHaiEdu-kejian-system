"""Fail-closed NodeRun terminalization for PPT preparation errors."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.workflows.execution_port import SqlAlchemyWorkflowExecutionPort
from apps.api.workflows.models import NodeRun, WorkflowRun
from workflow.node_state import NodeStatus


def terminalize_prepare_failure(
    session: Session,
    actor: ActorContext,
    workflow: SqlAlchemyWorkflowExecutionPort,
    node_run_id: UUID,
    *,
    code: str,
) -> None:
    row = session.execute(
        select(NodeRun, WorkflowRun)
        .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
        .where(
            NodeRun.id == node_run_id,
            NodeRun.organization_id == actor.organization_id,
            NodeRun.deleted_at.is_(None),
            WorkflowRun.organization_id == actor.organization_id,
            WorkflowRun.deleted_at.is_(None),
        )
        .with_for_update(of=NodeRun)
    ).one_or_none()
    if row is None:
        return
    node, run = row
    if not actor.is_system:
        ProjectAccessService(session, actor).require(
            run.project_id,
            ProjectAction.GENERATE,
        )
    if node.status == NodeStatus.FAILED.value and node.last_error_code == code:
        return
    if node.status == NodeStatus.CANCEL_REQUESTED.value:
        workflow.terminalize(node_run_id, code=code, cancelled=True)
        return
    workflow.start(node_run_id)
    workflow.terminalize(node_run_id, code=code, cancelled=False)
