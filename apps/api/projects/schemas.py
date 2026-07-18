"""Project request and response schemas aligned with the shared OpenAPI contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.projects.policy_schemas import AutomationPolicyMode

AutomationMode = Literal["manual", "assisted", "automatic"]


class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    knowledge_point: str = Field(min_length=1, max_length=255)
    grade: str | None = Field(default=None, max_length=40)
    textbook_edition: str | None = Field(default=None, max_length=120)
    automation_mode: AutomationMode | None = None
    execution_mode: AutomationPolicyMode | None = None

    @model_validator(mode="after")
    def select_execution_mode(self) -> CreateProjectRequest:
        if self.automation_mode is not None and self.execution_mode is not None:
            raise ValueError("automation_mode and execution_mode are mutually exclusive")
        if self.automation_mode is None and self.execution_mode is None:
            self.execution_mode = "guided"
        return self


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    subject: Literal["primary_math"]
    grade: str | None
    textbook_edition: str | None
    knowledge_point: str
    status: Literal["draft", "active", "archived"]
    automation_mode: AutomationMode
    content_release_id: UUID
    workflow_definition_version_id: UUID
    created_at: datetime
    updated_at: datetime


class ProjectEnvelope(BaseModel):
    data: ProjectRead
    request_id: str


class ProjectListData(BaseModel):
    items: list[ProjectRead]


class PageMeta(BaseModel):
    next_cursor: str | None


class ProjectListEnvelope(BaseModel):
    data: ProjectListData
    meta: PageMeta
    request_id: str
