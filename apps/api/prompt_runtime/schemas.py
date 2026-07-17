"""Public privacy-safe prompt preview schemas."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LockedLayerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: Literal["platform_safety", "output_schema", "provider_format"]
    key: str
    locked: Literal[True]


class ContextBindingSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_key: str
    source: str
    exposure: Literal["full", "summary", "hidden"]
    item_count: int = Field(ge=0)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class PromptPreviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    prompt_snapshot_id: UUID
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    editable_prompt: str
    locked_layers: list[LockedLayerSummary]
    context_summary: list[ContextBindingSummary]
    request_schema: dict[str, Any] | None = Field(default=None, alias="schema")


class PromptPreviewEnvelope(BaseModel):
    data: PromptPreviewRead
    request_id: str
