"""Tenant-scoped workflow runtime persistence queries."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowRun


class WorkflowRuntimeRepository:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def get_run(self, run_id: UUID, *, for_update: bool = False) -> WorkflowRun | None:
        statement = select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.organization_id == self._actor.organization_id,
            WorkflowRun.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def latest_for_project(self, project_id: UUID) -> WorkflowRun | None:
        return self._session.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.project_id == project_id,
                WorkflowRun.organization_id == self._actor.organization_id,
                WorkflowRun.deleted_at.is_(None),
            )
            .order_by(WorkflowRun.run_no.desc())
            .limit(1)
        )

    def active_for_project(self, project_id: UUID, *, for_update: bool) -> WorkflowRun | None:
        statement = select(WorkflowRun).where(
            WorkflowRun.project_id == project_id,
            WorkflowRun.organization_id == self._actor.organization_id,
            WorkflowRun.status.in_(("active", "paused")),
            WorkflowRun.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def next_run_no(self, project_id: UUID) -> int:
        return (
            int(
                self._session.scalar(
                    select(func.coalesce(func.max(WorkflowRun.run_no), 0)).where(
                        WorkflowRun.project_id == project_id
                    )
                )
                or 0
            )
            + 1
        )

    def list_nodes(self, workflow_run_id: UUID) -> list[NodeRun]:
        return list(
            self._session.scalars(
                select(NodeRun)
                .where(
                    NodeRun.workflow_run_id == workflow_run_id,
                    NodeRun.organization_id == self._actor.organization_id,
                    NodeRun.deleted_at.is_(None),
                )
                .order_by(NodeRun.node_key, NodeRun.run_no)
            )
        )

    def get_node(self, node_id: UUID, *, for_update: bool = False) -> NodeRun | None:
        statement = select(NodeRun).where(
            NodeRun.id == node_id,
            NodeRun.organization_id == self._actor.organization_id,
            NodeRun.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def next_node_run_no(
        self,
        workflow_run_id: UUID,
        branch_run_id: UUID | None,
        node_key: str,
    ) -> int:
        statement = select(func.coalesce(func.max(NodeRun.run_no), 0)).where(
            NodeRun.workflow_run_id == workflow_run_id,
            NodeRun.node_key == node_key,
        )
        if branch_run_id is None:
            statement = statement.where(NodeRun.branch_run_id.is_(None))
        else:
            statement = statement.where(NodeRun.branch_run_id == branch_run_id)
        return int(self._session.scalar(statement) or 0) + 1

    def active_node(
        self,
        workflow_run_id: UUID,
        branch_run_id: UUID | None,
        node_key: str,
    ) -> NodeRun | None:
        statement = select(NodeRun).where(
            NodeRun.workflow_run_id == workflow_run_id,
            NodeRun.node_key == node_key,
            NodeRun.status.in_(("queued", "running", "cancel_requested")),
            NodeRun.deleted_at.is_(None),
        )
        if branch_run_id is None:
            statement = statement.where(NodeRun.branch_run_id.is_(None))
        else:
            statement = statement.where(NodeRun.branch_run_id == branch_run_id)
        return self._session.scalar(statement.with_for_update())

    def list_branches(self, workflow_run_id: UUID) -> list[BranchRun]:
        return list(
            self._session.scalars(
                select(BranchRun)
                .where(
                    BranchRun.workflow_run_id == workflow_run_id,
                    BranchRun.deleted_at.is_(None),
                )
                .order_by(BranchRun.lesson_unit_id, BranchRun.branch_key)
            )
        )
