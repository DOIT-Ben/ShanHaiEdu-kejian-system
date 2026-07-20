"""Value parsing and freezing helpers for workflow definitions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any, cast

from workflow.definition import WorkflowDefinitionError


def freeze_workflow_value(value: object) -> object:
    if isinstance(value, Mapping):
        entries = cast(Mapping[object, object], value)
        frozen: dict[str, object] = {}
        for key, child in entries.items():
            if type(key) is not str:
                raise WorkflowDefinitionError(
                    "workflow binding keys must be strings",
                    code="WORKFLOW_NODE_DECLARATION_INVALID",
                )
            frozen[key] = freeze_workflow_value(child)
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(freeze_workflow_value(child) for child in cast(Sequence[object], value))
    return value


def as_mapping(value: object) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    entries = cast(Mapping[object, object], value)
    if any(type(key) is not str for key in entries):
        return None
    return cast(Mapping[str, Any], value)


def require_sequence(value: object, field: str) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise WorkflowDefinitionError(
            f"workflow output index field {field} must be an array",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return tuple(cast(Sequence[object], value))


def require_text(value: Mapping[str, Any] | None, field: str) -> str:
    if value is None:
        raise WorkflowDefinitionError(
            f"workflow output index field {field} is missing",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return require_text_value(value.get(field), field)


def require_text_value(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise WorkflowDefinitionError(
            f"workflow output index field {field} is invalid",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return value


def descriptor_identity(value: object) -> tuple[str, str, str]:
    mapping = as_mapping(value)
    if mapping is None:
        raise WorkflowDefinitionError(
            "workflow output index validator descriptor is invalid",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return (
        require_text(mapping, "key"),
        require_text(mapping, "semantic_version"),
        require_text(mapping, "implementation_digest"),
    )
