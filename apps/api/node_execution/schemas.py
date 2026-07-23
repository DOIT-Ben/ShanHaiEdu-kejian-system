"""Public command schemas for the existing node execution runtime."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StartNodeRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_revision: str | None = Field(default=None, min_length=1, max_length=20_000)


class NodeExecutionRead(BaseModel):
    node_run_id: UUID
    artifact_version_id: UUID
    creation_package_id: UUID | None
    attempt_id: UUID | None
    usage_id: UUID | None


class NodeExecutionEnvelope(BaseModel):
    data: NodeExecutionRead
    request_id: str
