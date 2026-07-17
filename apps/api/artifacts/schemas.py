"""Artifact HTTP request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateArtifactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_key: str = Field(min_length=1, max_length=160)
    artifact_type: str = Field(min_length=1, max_length=80)
    branch_key: str = Field(min_length=1, max_length=80)
    content_definition_version_id: UUID
    lesson_unit_id: UUID | None = None
    draft_branch: str = Field(default="main", min_length=1, max_length=80)
    content: dict[str, Any]


class SaveArtifactDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: dict[str, Any]


class SubmitArtifactVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_branch: str = Field(default="main", min_length=1, max_length=80)


class ReviewArtifactVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "request_changes", "revoke", "accept_stale"]
    comment: str | None = Field(default=None, max_length=4000)


class ArtifactDraftRead(BaseModel):
    id: UUID
    draft_branch: str
    content: dict[str, Any]
    validation_report: dict[str, Any]
    based_on_version_id: UUID | None
    autosaved_at: datetime
    lock_version: int


class ArtifactVersionRead(BaseModel):
    id: UUID
    version_no: int
    content: dict[str, Any]
    content_hash: str
    render_summary: dict[str, Any]
    source_kind: Literal["manual", "model", "import", "system"]
    source_node_run_id: UUID | None
    context_snapshot_id: UUID | None
    prompt_snapshot_id: UUID | None
    validation_report: dict[str, Any]
    created_at: datetime
    created_by: UUID


class ArtifactRead(BaseModel):
    id: UUID
    project_id: UUID
    lesson_unit_id: UUID | None
    branch_key: str
    artifact_key: str
    artifact_type: str
    content_definition_version_id: UUID
    status: Literal["draft", "in_review", "approved", "stale", "archived"]
    stale_reason: dict[str, Any] | None
    lock_version: int
    current_draft: ArtifactDraftRead | None
    current_submitted_version: ArtifactVersionRead | None
    current_approved_version: ArtifactVersionRead | None
    created_at: datetime
    updated_at: datetime


class ApprovalRead(BaseModel):
    id: UUID
    artifact_version_id: UUID
    action: Literal["submit", "approve", "request_changes", "revoke", "accept_stale"]
    actor_type: Literal["user", "system"]
    actor_user_id: UUID | None
    comment: str | None
    quality_evidence: dict[str, Any]
    policy_snapshot: dict[str, Any]
    created_at: datetime


class ArtifactEnvelope(BaseModel):
    data: ArtifactRead
    request_id: str


class ArtifactDraftEnvelope(BaseModel):
    data: ArtifactDraftRead
    request_id: str


class ArtifactVersionEnvelope(BaseModel):
    data: ArtifactVersionRead
    request_id: str


class ApprovalEnvelope(BaseModel):
    data: ApprovalRead
    request_id: str
