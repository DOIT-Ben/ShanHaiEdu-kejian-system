"""Workflow-owned fixed NodeRun facts for policy default Intro selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowRun


@dataclass(frozen=True, slots=True)
class IntroSelectionPolicySourceFact:
    node_run_id: UUID
    workflow_definition_version_id: UUID
    policy_version: int
    mode: object
    node_rules: object


class IntroSelectionWorkflowReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require_policy_source(
        self,
        *,
        node_run_id: UUID,
        project_id: UUID,
        lesson_unit_id: UUID,
    ) -> IntroSelectionPolicySourceFact:
        if not self._actor.is_system:
            raise _denied("Only the system actor can execute policy default selection.")
        row = self._session.execute(
            select(NodeRun, WorkflowRun)
            .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
            .join(BranchRun, BranchRun.id == NodeRun.branch_run_id)
            .where(
                NodeRun.id == node_run_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.node_key == "intro.select",
                NodeRun.status == "ready",
                NodeRun.deleted_at.is_(None),
                WorkflowRun.project_id == project_id,
                WorkflowRun.organization_id == self._actor.organization_id,
                WorkflowRun.status == "active",
                WorkflowRun.deleted_at.is_(None),
                BranchRun.lesson_unit_id == lesson_unit_id,
                BranchRun.status == "active",
                BranchRun.deleted_at.is_(None),
            )
            .with_for_update(of=NodeRun)
        ).one_or_none()
        if row is None:
            raise _denied("The policy source is not the active Intro select NodeRun.")
        node, run = row
        snapshot = cast(Mapping[str, Any], node.automation_policy_snapshot_json)
        policy_version = snapshot.get("policy_version")
        workflow_definition_version_id = run.workflow_definition_version_id
        if (
            type(policy_version) is not int
            or policy_version <= 0
            or snapshot.get("workflow_definition_version_id") != str(workflow_definition_version_id)
        ):
            raise _denied("The NodeRun policy snapshot is invalid for this workflow.")
        return IntroSelectionPolicySourceFact(
            node_run_id=node.id,
            workflow_definition_version_id=workflow_definition_version_id,
            policy_version=policy_version,
            mode=snapshot.get("mode"),
            node_rules=snapshot.get("node_rules"),
        )


def _denied(message: str) -> ApiError:
    return ApiError(status_code=409, code="INTRO_POLICY_AUTO_SELECT_DENIED", message=message)
