"""Workflow-owned published and runtime facts exposed to artifact approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.workflows.models import NodeRun, WorkflowDefinitionVersion, WorkflowRun


@dataclass(frozen=True, slots=True)
class QualityValidateNodeFact:
    organization_id: UUID
    project_id: UUID
    content_release_id: UUID
    workflow_definition_version_id: UUID
    node_key: str
    status: str


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
