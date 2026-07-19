"""Public privacy-safe prompt preview schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PromptEditPolicyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["replace_editable_layer"]
    max_chars: int = Field(ge=1, le=100_000)


class PromptPreviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_snapshot_id: UUID
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    editable_prompt: str
    edit_policy: PromptEditPolicyRead


class PromptPreviewEnvelope(BaseModel):
    data: PromptPreviewRead
    request_id: str
