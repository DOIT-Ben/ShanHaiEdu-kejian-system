"""Lesson HTTP request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.lessons.domain import BranchKey


class LessonBranchRead(BaseModel):
    branch_key: BranchKey
    enabled: bool
    workflow_status: Literal["disabled", "not_ready"]
    settings: dict[str, Any]


class LessonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    lesson_key: str
    position: int
    title: str
    scope_summary: str
    objective_summary: str
    estimated_minutes: int | None
    source_division_version_id: UUID
    status: Literal["active", "archived"]
    lock_version: int
    branches: list[LessonBranchRead]
    created_at: datetime
    updated_at: datetime


class LessonEnvelope(BaseModel):
    data: LessonRead
    request_id: str


class LessonCollectionData(BaseModel):
    items: list[LessonRead]
    lock_version: int


class LessonCollectionEnvelope(BaseModel):
    data: LessonCollectionData
    request_id: str


class PrepareLessonDivisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: UUID
    material_parse_version_id: UUID
    page_start: int = Field(gt=0)
    page_end: int = Field(gt=0)
    duration_minutes: int = Field(default=40, ge=30, le=60)
    requested_lesson_count: int | None = Field(default=None, ge=1, le=20)
    special_requirements: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def require_ordered_pages(self) -> PrepareLessonDivisionRequest:
        if self.page_end < self.page_start:
            raise ValueError("page_end must not be before page_start")
        return self


class LessonDivisionPreparationRead(BaseModel):
    material_scope_artifact_id: UUID
    material_scope_version_id: UUID
    generate_node_run_id: UUID
    validate_node_run_id: UUID
    gate_node_run_id: UUID


class LessonDivisionPreparationEnvelope(BaseModel):
    data: LessonDivisionPreparationRead
    request_id: str


class LessonCollectionItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    position: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    scope_summary: str = Field(min_length=1)
    objective_summary: str = Field(min_length=1)
    estimated_minutes: int | None = Field(gt=0)


class UpdateLessonCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[LessonCollectionItemUpdate] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_contiguous_items(self) -> UpdateLessonCollectionRequest:
        ids = [item.id for item in self.items]
        positions = [item.position for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("lesson ids must be unique")
        if len(positions) != len(set(positions)):
            raise ValueError("lesson positions must be unique")
        if sorted(positions) != list(range(1, len(positions) + 1)):
            raise ValueError("lesson positions must be contiguous starting at one")
        return self


class LessonBranchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_key: BranchKey
    enabled: bool
    settings: dict[str, Any]


class UpdateLessonBranchesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branches: list[LessonBranchUpdate] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def require_unique_branch_keys(self) -> UpdateLessonBranchesRequest:
        keys = [branch.branch_key for branch in self.branches]
        if len(keys) != len(set(keys)):
            raise ValueError("branch_key values must be unique")
        return self
