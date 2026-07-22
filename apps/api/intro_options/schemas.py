"""Public HTTP schemas for Intro options and teacher selections."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IntroOptionSetPublicRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_mode: Literal["default_nine", "refine_existing"]
    lesson_unit_key: str = Field(min_length=1)
    knowledge_point: str = Field(min_length=1)
    options: list[dict[str, Any]] = Field(min_length=1, max_length=9)
    created_at: datetime


class IntroOptionVersionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_version_id: UUID
    version_no: int = Field(gt=0)
    approval_status: Literal[
        "approved",
        "pending_review",
        "changes_requested",
        "revoked",
        "unapproved",
    ]
    stale: bool
    selectable: bool
    option_set: IntroOptionSetPublicRead


class IntroSelectionPublicRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection_id: UUID
    artifact_version_id: UUID
    option_key: str = Field(min_length=1)
    selection_method: Literal["teacher_selected", "policy_default"]
    snapshot: dict[str, Any]
    reason: str = Field(min_length=1)
    active: bool
    consumable: bool
    unconsumable_reason: str | None
    selected_at: datetime
    deactivated_at: datetime | None


class IntroOptionsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    current_approved_version_id: UUID | None
    display_version: IntroOptionVersionRead | None
    pending_version: IntroOptionVersionRead | None
    current_selection: IntroSelectionPublicRead | None


class IntroOptionsEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: IntroOptionsRead
    request_id: str = Field(min_length=1)


class SelectIntroOptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_version_id: UUID
    option_key: str = Field(min_length=1, max_length=120)


class IntroSelectionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: IntroSelectionPublicRead
    request_id: str = Field(min_length=1)
