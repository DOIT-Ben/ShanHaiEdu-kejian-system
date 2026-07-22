"""Application reads for Intro selection facts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IntroSelectionRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    lesson_unit_id: UUID
    artifact_version_id: UUID
    source_approval_id: UUID
    selection_method: Literal["teacher_selected", "policy_default"]
    option_key: str
    snapshot: dict[str, Any]
    actor_type: Literal["user", "system"]
    actor_user_id: UUID | None
    policy_evidence: dict[str, Any]
    recommendation_evidence: dict[str, Any]
    reason: str
    active: bool
    consumable: bool
    unconsumable_reason: str | None
    selected_at: datetime
    deactivated_at: datetime | None
