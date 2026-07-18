"""Versioned automation policy contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AutomationPolicyMode = Literal["guided", "automatic"]


class AutomationNodeRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_key: str = Field(min_length=1, max_length=120)
    auto_start: bool | None = None
    auto_submit: bool | None = None
    auto_approve: bool | None = None
    auto_adopt: bool | None = None
    auto_save_to_project: bool | None = None
    pause_after: bool | None = None


class AutomationPolicyRead(BaseModel):
    project_id: UUID
    workflow_definition_version_id: UUID
    mode: AutomationPolicyMode
    node_rules: list[AutomationNodeRule]
    policy_version: int
    updated_at: datetime


class AutomationPolicyEnvelope(BaseModel):
    data: AutomationPolicyRead
    request_id: str


class UpdateAutomationPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: AutomationPolicyMode | None = None
    node_rules: list[AutomationNodeRule] | None = None

    @model_validator(mode="after")
    def require_change(self) -> UpdateAutomationPolicyRequest:
        if self.mode is None and self.node_rules is None:
            raise ValueError("at least one automation policy field is required")
        return self


MANUAL_DISABLED_RULE = AutomationNodeRule(
    node_key="*",
    auto_start=False,
    auto_submit=False,
    auto_approve=False,
    auto_adopt=False,
    auto_save_to_project=False,
    pause_after=True,
)


def initial_policy_values(
    *,
    execution_mode: AutomationPolicyMode | None,
    automation_mode: Literal["manual", "assisted", "automatic"] | None,
) -> tuple[AutomationPolicyMode, list[dict[str, object]]]:
    if execution_mode is not None:
        return execution_mode, []
    if automation_mode == "manual":
        return "guided", [MANUAL_DISABLED_RULE.model_dump(exclude_none=True)]
    if automation_mode == "automatic":
        return "automatic", []
    return "guided", []
