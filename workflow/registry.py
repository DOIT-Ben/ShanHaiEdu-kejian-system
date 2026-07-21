"""Public workflow registry facade with deterministic contract resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from workflow.definition import WorkflowDefinitionError
from workflow.registry_legacy import load_legacy_workflow
from workflow.registry_runtime import RegisteredWorkflow, load_current_workflow

WORKFLOW_CATALOG_API_VERSION = "shanhai.workflow-node-generation-binding/v2"
LEGACY_WORKFLOW_CATALOG_API_VERSION = "shanhai.workflow-node-generation-binding/v1"

__all__ = [
    "BUILTIN_WORKFLOW_REGISTRY",
    "LEGACY_WORKFLOW_CATALOG_API_VERSION",
    "WORKFLOW_CATALOG_API_VERSION",
    "RegisteredWorkflow",
    "WorkflowRegistry",
]


@dataclass(frozen=True, slots=True)
class WorkflowRegistry:
    """Load a published graph without embedding business contract allowlists."""

    available_contract_refs: frozenset[str] | None = None

    def load(self, payload: dict[str, Any]) -> RegisteredWorkflow:
        api_version = payload.get("api_version")
        if api_version == WORKFLOW_CATALOG_API_VERSION:
            return load_current_workflow(
                payload,
                available_contract_refs=self.available_contract_refs,
            )
        if api_version == LEGACY_WORKFLOW_CATALOG_API_VERSION or api_version is None:
            return load_legacy_workflow(payload)
        raise WorkflowDefinitionError(
            "unsupported release: workflow catalog must use a supported declaration",
            code="WORKFLOW_RELEASE_UNSUPPORTED",
        )


BUILTIN_WORKFLOW_REGISTRY = WorkflowRegistry()
