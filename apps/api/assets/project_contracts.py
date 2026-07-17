"""Stable declarations for project asset slots and binding commands."""

from __future__ import annotations

import re
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SEMANTIC_KEY_PATTERN = r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$"
MIME_TYPE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]*/(?:\*|[a-z0-9][a-z0-9!#$&^_.+-]*)$")


class AssetCardinality(StrEnum):
    ONE = "one"
    MANY = "many"


class ReplaceMode(StrEnum):
    REJECT_IF_OCCUPIED = "reject_if_occupied"
    REPLACE_ACTIVE = "replace_active"
    APPEND = "append"


class AssetTargetContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_mime_types: tuple[str, ...] = ()
    require_clean_scan: bool = True

    @field_validator("allowed_mime_types")
    @classmethod
    def validate_mime_types(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("allowed MIME types must be unique")
        if any(MIME_TYPE_PATTERN.fullmatch(value) is None for value in values):
            raise ValueError("allowed MIME types must use type/subtype syntax")
        return values


class AssetSlotDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_key: str = Field(min_length=1, max_length=160, pattern=SEMANTIC_KEY_PATTERN)
    lesson_unit_id: UUID | None = None
    asset_type: str = Field(min_length=1, max_length=80, pattern=SEMANTIC_KEY_PATTERN)
    cardinality: AssetCardinality
    required: bool = False
    target_contract: AssetTargetContract = Field(default_factory=AssetTargetContract)
