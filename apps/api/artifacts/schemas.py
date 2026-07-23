"""Artifact HTTP request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AllImpactScopeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["all"]


class KeyedImpactScopeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["keyed"]
    selector: Literal["lesson_key"]
    keys: list[str] = Field(min_length=1)

    @field_validator("keys")
    @classmethod
    def require_canonical_keys(cls, keys: list[str]) -> list[str]:
        if any(not key.strip() for key in keys):
            raise ValueError("keys must be non-empty")
        if len(set(keys)) != len(keys) or keys != sorted(keys):
            raise ValueError("keys must be unique and sorted")
        return keys


ArtifactImpactScopeRead = Annotated[
    AllImpactScopeRead | KeyedImpactScopeRead,
    Field(discriminator="mode"),
]


class ArtifactStaleBindingRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_type: Literal["derives_from", "references", "constrains"]
    binding_key: str = Field(min_length=1, max_length=160)
    impact_scope: ArtifactImpactScopeRead


class ArtifactStaleReasonRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: Literal["UPSTREAM_APPROVED_VERSION_CHANGED", "UPSTREAM_APPROVAL_REVOKED"]
    replaced_upstream_version_id: UUID
    replacement_version_id: UUID | None
    bindings: list[ArtifactStaleBindingRead] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_replacement(self) -> ArtifactStaleReasonRead:
        is_revoke = self.reason_code == "UPSTREAM_APPROVAL_REVOKED"
        if is_revoke != (self.replacement_version_id is None):
            raise ValueError("replacement_version_id does not match reason_code")
        return self


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
    stale_reason: ArtifactStaleReasonRead | None
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


class ArtifactListData(BaseModel):
    items: list[ArtifactRead]


class ArtifactListEnvelope(BaseModel):
    data: ArtifactListData
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
