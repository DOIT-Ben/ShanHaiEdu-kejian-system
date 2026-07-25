"""Workflow aggregate response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.artifacts.schemas import ArtifactStaleReasonRead
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
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    workflow_run_id: UUID
    branch_run_id: UUID | None
    node_key: str
    run_no: int
    status: NodeStatus
    stale_reason: ArtifactStaleReasonRead | None = Field(validation_alias="stale_reason_json")
    started_at: datetime | None
    finished_at: datetime | None


class NodeRunEnvelope(BaseModel):
    data: NodeRunRead
    request_id: str


class AcceptedNodeRunData(BaseModel):
    node_run_id: UUID
    status: NodeStatus
    events_url: str


class AcceptedNodeRunEnvelope(BaseModel):
    data: AcceptedNodeRunData
    request_id: str


class StartNodeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_revision: str | None = Field(default=None, max_length=6_000)


class WorkflowAggregateData(BaseModel):
    project: ProjectRead
    workflow_run: WorkflowRunRead | None
    lessons: list[dict[str, Any]]
    node_runs: list[NodeRunRead]


class WorkflowEnvelope(BaseModel):
    data: WorkflowAggregateData
    request_id: str
