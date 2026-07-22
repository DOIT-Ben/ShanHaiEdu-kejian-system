"""Workflow-owned retirement of branch NodeRun history."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.identity.context import ActorContext
from apps.api.workflows.models import BranchRun, NodeRun
from apps.api.workflows.service import WorkflowRuntimeService

_ACTIVE_EXECUTION_STATUSES = frozenset({"queued", "running", "cancel_requested"})


class BranchNodeActiveError(ValueError):
    """Raised when branch retirement encounters an active execution."""


class BranchNodeLifecycle:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def touch(self, branch: BranchRun) -> None:
        branch.updated_at = utc_now()
        branch.updated_by = self._actor.principal_id
        branch.lock_version += 1

    def require_idle(self, branch_run_id: UUID) -> None:
        active = self._session.scalar(
            select(NodeRun.id)
            .where(
                NodeRun.branch_run_id == branch_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.status.in_(_ACTIVE_EXECUTION_STATUSES),
                NodeRun.deleted_at.is_(None),
            )
            .order_by(NodeRun.id)
            .limit(1)
            .with_for_update()
        )
        if active is not None:
            raise BranchNodeActiveError("the lesson branch still has an active execution")

    def retire(
        self,
        branch_run_id: UUID,
        *,
        review_completion: bool,
    ) -> int:
        nodes = list(
            self._session.scalars(
                select(NodeRun)
                .where(
                    NodeRun.branch_run_id == branch_run_id,
                    NodeRun.organization_id == self._actor.organization_id,
                    NodeRun.deleted_at.is_(None),
                )
                .order_by(NodeRun.id)
                .with_for_update(of=NodeRun)
            )
        )
        runtime = WorkflowRuntimeService(self._session, self._actor)
        changed = 0
        for node in nodes:
            previous = node.status
            runtime.retire_branch_node(
                node.id,
                review_completion=review_completion,
            )
            changed += int(node.status != previous)
        return changed
