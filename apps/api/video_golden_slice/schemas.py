from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from apps.api.jobs.schemas import GenerationJobRead


class StartVideoGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyframe_file_asset_version_id: UUID


class SaveVideoAdoptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    replace_mode: Literal["replace_active"]


class VideoGoldenSliceCandidate(BaseModel):
    result_id: UUID
    file_asset_version_id: UUID
    mime_type: str
    byte_size: int
    sha256: str
    duration_ms: int
    playback_url: str
    adoption_id: UUID | None
    saved_binding_id: UUID | None


class VideoGoldenSlice(BaseModel):
    project_id: UUID
    lesson_unit_id: UUID
    intro_selection_id: UUID
    intro_artifact_version_id: UUID
    keyframe_file_asset_version_id: UUID | None
    keyframe_slot_key: str | None
    job: GenerationJobRead | None
    candidate: VideoGoldenSliceCandidate | None


class VideoGoldenSliceEnvelope(BaseModel):
    data: VideoGoldenSlice
    request_id: str
