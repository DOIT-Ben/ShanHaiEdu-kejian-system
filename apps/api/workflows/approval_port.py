"""Workflow-owned published and runtime facts exposed to artifact approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
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
from apps.api.workflows.service import WorkflowRuntimeError, WorkflowRuntimeService
from workflow.node_state import NodeStatus


@dataclass(frozen=True, slots=True)
class QualityValidateNodeFact:
    organization_id: UUID
    project_id: UUID
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_key: str
    status: str


@dataclass(frozen=True, slots=True)
class ArtifactApprovalGateCommand:
    project_id: UUID
    lesson_unit_id: UUID
    artifact_version_id: UUID
    content_release_id: UUID
    workflow_definition_version_id: UUID
    gate_node_key: str
    branch_key: str
    source_input_ref: str


class WorkflowArtifactApprovalPort:
    """Complete or retire one exact lesson-scoped human gate."""

    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def complete(self, command: ArtifactApprovalGateCommand) -> None:
        gate = self._exact_gate(command)
        if gate is None:
            raise self._invalid("The exact artifact approval gate is unavailable.")
        try:
            WorkflowRuntimeService(self._session, self._actor).approve_review_gate(gate.id)
        except WorkflowRuntimeError as exc:
            raise self._invalid(str(exc)) from exc

    def retire_if_present(
        self,
        command: ArtifactApprovalGateCommand,
        *,
        review_completion: bool,
    ) -> bool:
        gate = self._exact_gate(command, required=False)
        if gate is None:
            return False
        if NodeStatus(gate.status) is not NodeStatus.REVIEW_REQUIRED:
            raise self._invalid("The exact artifact approval gate is not reviewable.")
        try:
            WorkflowRuntimeService(self._session, self._actor).retire_branch_node(
                gate.id,
                review_completion=review_completion,
            )
        except WorkflowRuntimeError as exc:
            raise self._invalid(str(exc)) from exc
        return True

    def _exact_gate(
        self,
        command: ArtifactApprovalGateCommand,
        *,
        required: bool = True,
    ) -> NodeRun | None:
        rows = list(
            self._session.scalars(
                select(NodeRun)
                .join(BranchRun, BranchRun.id == NodeRun.branch_run_id)
                .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
                .join(NodeInputSnapshot, NodeInputSnapshot.node_run_id == NodeRun.id)
                .where(
                    NodeRun.organization_id == self._actor.organization_id,
                    NodeRun.node_key == command.gate_node_key,
                    NodeRun.deleted_at.is_(None),
                    BranchRun.lesson_unit_id == command.lesson_unit_id,
                    BranchRun.branch_key == command.branch_key,
                    BranchRun.deleted_at.is_(None),
                    WorkflowRun.project_id == command.project_id,
                    WorkflowRun.content_release_id == command.content_release_id,
                    WorkflowRun.workflow_definition_version_id
                    == command.workflow_definition_version_id,
                    NodeInputSnapshot.input_key == command.source_input_ref,
                    NodeInputSnapshot.source_version_id == command.artifact_version_id,
                )
                .order_by(NodeRun.run_no.desc())
                .with_for_update(of=NodeRun)
            )
        )
        if len(rows) > 1 or (required and not rows):
            raise self._invalid("The exact artifact approval gate identity is invalid.")
        return rows[0] if rows else None

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=409, code="ARTIFACT_APPROVAL_GATE_INVALID", message=message)


class WorkflowApprovalReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def published_graph(self, workflow_definition_version_id: UUID) -> dict[str, Any] | None:
        workflow = self._session.get(
            WorkflowDefinitionVersion,
            workflow_definition_version_id,
        )
        if workflow is None or workflow.status != "published":
            return None
        return dict(workflow.graph_json)

    def fixed_release_for_node(
        self,
        node_run_id: UUID,
        *,
        organization_id: UUID,
        project_id: UUID,
    ) -> tuple[UUID, UUID] | None:
        row = self._session.execute(
            select(
                WorkflowRun.content_release_id,
                WorkflowRun.workflow_definition_version_id,
            )
            .join(NodeRun, NodeRun.workflow_run_id == WorkflowRun.id)
            .where(
                NodeRun.id == node_run_id,
                NodeRun.organization_id == organization_id,
                NodeRun.deleted_at.is_(None),
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.project_id == project_id,
                WorkflowRun.deleted_at.is_(None),
            )
        ).one_or_none()
        return None if row is None else (row[0], row[1])

    def validate_node_fact(self, node_run_id: UUID) -> QualityValidateNodeFact | None:
        row = self._session.execute(
            select(NodeRun, WorkflowRun)
            .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
            .where(NodeRun.id == node_run_id)
        ).one_or_none()
        if row is None:
            return None
        node, run = row
        return QualityValidateNodeFact(
            organization_id=node.organization_id,
            project_id=run.project_id,
            content_release_id=run.content_release_id,
            workflow_definition_version_id=run.workflow_definition_version_id,
            node_key=node.node_key,
            status=node.status,
        )
