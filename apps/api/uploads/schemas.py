"""Upload request and response schemas aligned with the shared OpenAPI contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateUploadSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class UploadSessionRead(BaseModel):
    upload_session_id: UUID
    material_id: UUID
    upload_url: str
    method: Literal["PUT"] = "PUT"
    required_headers: dict[str, str]
    expires_at: datetime


class UploadSessionEnvelope(BaseModel):
    data: UploadSessionRead
    request_id: str


class ConfirmUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_session_id: UUID
    etag: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class SourceMaterialRead(BaseModel):
    id: UUID
    original_filename: str
    mime_type: str
    upload_status: Literal["pending_upload", "confirmed", "rejected"]
    confirmed_at: datetime | None


class SourceMaterialListData(BaseModel):
    items: list[SourceMaterialRead]


class SourceMaterialListEnvelope(BaseModel):
    data: SourceMaterialListData
    request_id: str
