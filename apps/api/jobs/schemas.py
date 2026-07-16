"""Generation job response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

JobStatus = Literal[
    "created",
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancel_requested",
    "cancelled",
]


class GenerationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None
    job_type: str
    status: JobStatus
    progress_percent: int
    progress_message: str | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class GenerationJobEnvelope(BaseModel):
    data: GenerationJobRead
    request_id: str


class AcceptedJobData(BaseModel):
    job_id: UUID
    status: Literal["created", "queued", "running"]
    events_url: str


class AcceptedJobEnvelope(BaseModel):
    data: AcceptedJobData
    request_id: str
