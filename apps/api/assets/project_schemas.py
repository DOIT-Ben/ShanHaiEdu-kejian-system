"""Public project asset slot and binding API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetTargetContract,
    ReplaceMode,
)


class BindAssetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_asset_version_id: UUID
    source_artifact_version_id: UUID | None
    replace_mode: ReplaceMode
    position: int | None = Field(ge=0)


class AssetBindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_asset_slot_id: UUID
    file_asset_version_id: UUID
    source_artifact_version_id: UUID | None
    position: int
    is_active: bool
    bound_at: datetime
    bound_by: UUID
    unbound_at: datetime | None
    unbound_by: UUID | None


class ProjectAssetSlotRead(BaseModel):
    id: UUID
    project_id: UUID
    lesson_unit_id: UUID | None
    slot_key: str
    asset_type: str
    cardinality: AssetCardinality
    required: bool
    status: Literal["empty", "satisfied"]
    target_contract: AssetTargetContract
    active_bindings: list[AssetBindingRead]


class AssetBindingEnvelope(BaseModel):
    data: AssetBindingRead
    request_id: str


class ProjectAssetSlotListData(BaseModel):
    items: list[ProjectAssetSlotRead]


class AssetPageMeta(BaseModel):
    next_cursor: str | None


class ProjectAssetSlotListEnvelope(BaseModel):
    data: ProjectAssetSlotListData
    meta: AssetPageMeta
    request_id: str


class ProjectAssetPackageData(BaseModel):
    project_id: UUID
    items: list[ProjectAssetSlotRead]


class ProjectAssetPackageEnvelope(BaseModel):
    data: ProjectAssetPackageData
    meta: AssetPageMeta
    request_id: str
