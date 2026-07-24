"""Public request and response models for teacher sessions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_code: str = Field(min_length=1, max_length=512)


class SessionPrincipal(BaseModel):
    principal_id: UUID
    user_id: UUID
    organization_id: UUID
    display_name: str
    organization_name: str
    organization_role: str


class CurrentSession(BaseModel):
    session_id: UUID
    principal: SessionPrincipal
    expires_at: datetime
    csrf_token: str


class SessionEnvelope(BaseModel):
    data: CurrentSession
    request_id: str
