"""Declarative workflow graph definitions and publication validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

PROJECT_BRANCH_KEYS = frozenset({"material", "lesson_division", "delivery"})
LESSON_UNIT_BRANCH_KEYS = frozenset({"lesson_plan", "intro_options", "ppt", "video"})


class WorkflowDefinitionError(ValueError):
    """Raised when a workflow graph cannot be safely published."""

    def __init__(self, message: str, *, code: str = "WORKFLOW_DEFINITION_INVALID") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class WorkflowNodeDefinition:
    node_key: str
    execution_kind: str
    execution_scope: str
    branch_key: str | None
    entrypoint: bool
    dependencies: tuple[str, ...]
    input_contract_refs: tuple[str, ...]
    output_contract_refs: tuple[str, ...]
    binding: Mapping[str, Any]
    optional_input_contract_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowGraph:
    nodes: tuple[WorkflowNodeDefinition, ...]


@dataclass(frozen=True, slots=True)
class WorkflowProducerRef:
    """A contract producer retained with its topology identity."""

    node_key: str
    execution_scope: str
    branch_key: str
    output_contract_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WorkflowOutputDefinitionBinding:
    """The immutable reverse entry for one published model output definition."""

    content_definition_key: str
    generation_template_key: str
    producer_node_key: str
    execution_scope: str
    producer_branch_key: str
    artifact_branch_key: str
    artifact_type: str
    output_contract_refs: tuple[str, ...]
    quality_validate_node_key: str | None
    quality_report_refs: tuple[str, ...]
    quality_validator_refs: tuple[tuple[str, str, str], ...]
    quality_gate_node_key: str | None
    quality_requirement_mode: str
    approval_completion: WorkflowApprovalCompletionBinding | None


@dataclass(frozen=True, slots=True)
class WorkflowApprovalCompletionBinding:
    """Explicit application effect attached to an approved generated output."""

    kind: str
    collection_pointer: str | None
    stable_key_field: str | None
    source_input_ref: str | None


@dataclass(frozen=True, slots=True)
class WorkflowIndexes:
    """Derived immutable indexes used by runtime consumers."""

    producers_by_contract: Mapping[str, tuple[WorkflowProducerRef, ...]]
    producer_index: Mapping[tuple[str, str, str], WorkflowProducerRef]
    output_definition_index: Mapping[str, WorkflowOutputDefinitionBinding]


def freeze_workflow_value(value: object) -> object:
    """Recursively freeze a validated JSON workflow snapshot."""

    from workflow.definition_values import freeze_workflow_value as freeze_value

    return freeze_value(value)


def validate_workflow_graph(
    graph: WorkflowGraph,
    *,
    available_contract_refs: frozenset[str] | None = None,
) -> tuple[str, ...]:
    from workflow.definition_topology import validate_workflow_graph as validate_graph

    return validate_graph(graph, available_contract_refs=available_contract_refs)


def build_workflow_indexes(graph: WorkflowGraph) -> WorkflowIndexes:
    """Build branch-scoped producers and ContentDefinition reverse entries."""

    from workflow.definition_indexes import build_workflow_indexes as build_indexes

    return build_indexes(graph)
