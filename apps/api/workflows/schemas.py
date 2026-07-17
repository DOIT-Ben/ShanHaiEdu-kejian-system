"""Workflow aggregate response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.api.projects.schemas import ProjectRead
from workflow.node_state import NodeStatus


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_no: int
    status: Literal["active", "paused", "completed", "failed", "cancelled"]
    content_release_id: UUID
    workflow_definition_version_id: UUID
    started_at: datetime
    completed_at: datetime | None


class NodeRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_run_id: UUID
    branch_run_id: UUID | None
    node_key: str
    run_no: int
    status: NodeStatus
    stale_reason: dict[str, Any] | None
    started_at: datetime | None
    finished_at: datetime | None


class WorkflowAggregateData(BaseModel):
    project: ProjectRead
    workflow_run: WorkflowRunRead | None
    lessons: list[dict[str, Any]]
    node_runs: list[NodeRunRead]


class WorkflowEnvelope(BaseModel):
    data: WorkflowAggregateData
    request_id: str
