"""Public creation lifecycle request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

StudioType = Literal["image", "video", "presentation"]
ReplaceModeValue = Literal["reject_if_occupied", "replace_active", "append"]


class LegacyCreateCreationBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    studio_type: StudioType
    title: str = Field(min_length=1, max_length=255)
    creation_package_id: UUID | None = None


class ProjectCreateCreationBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["project"]
    studio_type: StudioType
    title: str = Field(min_length=1, max_length=255)
    creation_package_id: UUID


class StandaloneCreateCreationBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["standalone"]
    studio_type: StudioType
    title: str = Field(min_length=1, max_length=255)


CurrentCreateCreationBatchRequest = Annotated[
    ProjectCreateCreationBatchRequest | StandaloneCreateCreationBatchRequest,
    Field(discriminator="source_kind"),
]
CreateCreationBatchRequest = (
    ProjectCreateCreationBatchRequest
    | StandaloneCreateCreationBatchRequest
    | LegacyCreateCreationBatchRequest
)


class ProjectCreationItemRead(BaseModel):
    id: UUID
    item_key: str
    title: str
    status: str
    current_prompt_version_id: UUID | None
    active_adoption_id: UUID | None
    target_slot_key: str


class StandaloneCreationItemRead(BaseModel):
    id: UUID
    item_key: str
    title: str
    status: str
    current_prompt_version_id: UUID | None
    active_adoption_id: UUID | None


class CreationPackageSourceRead(BaseModel):
    project_id: UUID
    workflow_run_id: UUID
    source_node_run_id: UUID


class ProjectCreationBatchRead(BaseModel):
    id: UUID
    source_kind: Literal["project"]
    creation_package_id: UUID
    source: CreationPackageSourceRead
    studio_type: StudioType
    title: str
    status: str
    items: list[ProjectCreationItemRead]


class StandaloneCreationBatchRead(BaseModel):
    id: UUID
    source_kind: Literal["standalone"]
    studio_type: StudioType
    title: str
    status: str
    items: list[StandaloneCreationItemRead]


CreationBatchRead = Annotated[
    ProjectCreationBatchRead | StandaloneCreationBatchRead,
    Field(discriminator="source_kind"),
]


class CreationBatchEnvelope(BaseModel):
    data: CreationBatchRead
    request_id: str


class SavePromptVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_prompt: str = Field(min_length=1, max_length=50000)
    reference_asset_version_ids: list[UUID] = Field(max_length=20)
    output_spec: dict[str, object]
    generation_profile: Literal["quality", "balanced", "speed"]


class PromptVersionRead(BaseModel):
    id: UUID
    creation_item_id: UUID
    version_no: int
    business_prompt: str
    reference_asset_version_ids: list[UUID]
    output_spec: dict[str, object]
    generation_profile: Literal["quality", "balanced", "speed"]
    content_hash: str
    created_at: datetime


class PromptVersionEnvelope(BaseModel):
    data: PromptVersionRead
    request_id: str


class GenerateCreationItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_version_id: UUID
    candidate_count: int = Field(default=1, ge=1, le=8)


class BatchGenerationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID
    prompt_version_id: UUID
    candidate_count: int = Field(default=1, ge=1, le=8)


class GenerateCreationBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[BatchGenerationItem] = Field(min_length=1, max_length=100)


class LegacyGenerateCreationBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: list[UUID] = Field(min_length=1)


class AdoptGenerationResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=1000)


class AdoptionRead(BaseModel):
    id: UUID
    creation_item_id: UUID
    generation_result_id: UUID
    adoption_mode: Literal["teacher", "automation_policy"]
    reason: str | None
    adopted_at: datetime


class AdoptionEnvelope(BaseModel):
    data: AdoptionRead
    request_id: str


class ProjectSourceSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["project"]
    replace_mode: ReplaceModeValue


class StandaloneSourceSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["standalone"]
    project_id: UUID
    slot_key: str = Field(min_length=1, max_length=160)
    replace_mode: ReplaceModeValue


SaveAdoptionToProjectRequest = Annotated[
    ProjectSourceSaveRequest | StandaloneSourceSaveRequest,
    Field(discriminator="source_kind"),
]


class SaveToProjectOperationRead(BaseModel):
    operation_id: UUID
    adoption_id: UUID
    status: Literal["completed"]
    binding_id: UUID
    target_project_id: UUID
    target_slot_key: str
    idempotent_replay: bool


class SaveToProjectOperationEnvelope(BaseModel):
    data: SaveToProjectOperationRead
    request_id: str


class LegacySaveGenerationResultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    slot_key: str = Field(min_length=1, max_length=160)
    replace_mode: ReplaceModeValue
