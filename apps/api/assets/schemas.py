"""Public file asset and material parse metadata schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class FileAssetVersionRead(BaseModel):
    id: UUID
    version_no: int
    mime_type: str
    byte_size: int
    sha256: str
    width: int | None
    height: int | None
    duration_ms: int | None
    page_count: int | None
    scan_status: Literal["pending", "clean", "rejected"]
    derived_from_version_id: UUID | None
    created_at: datetime


class FileAssetRead(BaseModel):
    id: UUID
    asset_key: str
    asset_kind: str
    status: Literal["pending", "active", "rejected"]
    retention_class: str
    lock_version: int
    current_version: FileAssetVersionRead


class FileAssetEnvelope(BaseModel):
    data: FileAssetRead
    request_id: str


class MaterialParseVersionRead(BaseModel):
    id: UUID
    source_material_id: UUID
    file_asset_version_id: UUID
    generation_job_id: UUID | None
    version_no: int
    status: Literal["pending", "running", "succeeded", "failed"]
    parser_name: str
    parser_version: str
    page_count: int | None
    text_checksum: str | None
    validation_report: dict[str, Any]
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class MaterialParseVersionListData(BaseModel):
    items: list[MaterialParseVersionRead]


class MaterialParseVersionListEnvelope(BaseModel):
    data: MaterialParseVersionListData
    request_id: str
