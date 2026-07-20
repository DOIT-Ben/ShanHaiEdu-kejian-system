"""Declarative workflow graph definitions and publication validation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast

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


@dataclass(frozen=True, slots=True)
class WorkflowIndexes:
    """Derived immutable indexes used by runtime consumers."""

    producers_by_contract: Mapping[str, tuple[WorkflowProducerRef, ...]]
    producer_index: Mapping[tuple[str, str, str], WorkflowProducerRef]
    output_definition_index: Mapping[str, WorkflowOutputDefinitionBinding]


def validate_workflow_graph(
    graph: WorkflowGraph,
    *,
    available_contract_refs: frozenset[str] | None = None,
) -> tuple[str, ...]:
    keys = [node.node_key for node in graph.nodes]
    if len(keys) != len(set(keys)):
        raise WorkflowDefinitionError(
            "workflow graph contains duplicate node_key values",
            code="WORKFLOW_NODE_KEY_DUPLICATE",
        )
    node_by_key = {node.node_key: node for node in graph.nodes}
    for node in graph.nodes:
        if not node.node_key.strip():
            raise WorkflowDefinitionError(
                "workflow node_key cannot be empty",
                code="WORKFLOW_NODE_DECLARATION_INVALID",
            )
        if node.execution_kind not in {"model_generation", "deterministic", "human_gate"}:
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has an invalid execution kind",
                code="WORKFLOW_NODE_KIND_INVALID",
            )
        if node.execution_scope not in {"project", "lesson_unit"}:
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has an invalid execution scope",
                code="WORKFLOW_NODE_SCOPE_INVALID",
            )
        if node.execution_scope == "project" and node.branch_key not in PROJECT_BRANCH_KEYS:
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has an invalid branch for project scope",
                code="WORKFLOW_NODE_BRANCH_INVALID",
            )
        if node.execution_scope == "lesson_unit" and node.branch_key not in LESSON_UNIT_BRANCH_KEYS:
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has an invalid branch for lesson_unit scope",
                code="WORKFLOW_NODE_BRANCH_INVALID",
            )
        if type(node.entrypoint) is not bool:
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} entrypoint must be a boolean",
                code="WORKFLOW_NODE_ENTRYPOINT_INVALID",
            )
        if len(node.dependencies) != len(set(node.dependencies)):
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} contains duplicate dependencies",
                code="WORKFLOW_DEPENDENCY_DUPLICATE",
            )
        if any(not dependency.strip() for dependency in node.dependencies):
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} contains an invalid dependency",
                code="WORKFLOW_DEPENDENCY_INVALID",
            )
        missing = set(node.dependencies) - node_by_key.keys()
        if missing:
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has missing dependencies: {sorted(missing)}",
                code="WORKFLOW_DEPENDENCY_MISSING",
            )
        if node.entrypoint != (not node.dependencies):
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} entrypoint does not match dependencies",
                code="WORKFLOW_ENTRYPOINT_INVALID",
            )
        for dependency in node.dependencies:
            dependency_node = node_by_key[dependency]
            if dependency_node.execution_scope != node.execution_scope:
                raise WorkflowDefinitionError(
                    f"workflow node {node.node_key} dependency {dependency} "
                    "crosses execution scope",
                    code="WORKFLOW_DEPENDENCY_SCOPE_INVALID",
                )
            if dependency_node.branch_key != node.branch_key:
                raise WorkflowDefinitionError(
                    f"workflow node {node.node_key} dependency {dependency} crosses branch",
                    code="WORKFLOW_DEPENDENCY_BRANCH_INVALID",
                )
        if available_contract_refs is not None:
            referenced = set(node.input_contract_refs) | set(node.output_contract_refs)
            missing_contracts = referenced - available_contract_refs
            if missing_contracts:
                raise WorkflowDefinitionError(
                    f"workflow node {node.node_key} has missing contract refs: "
                    f"{sorted(missing_contracts)}",
                    code="WORKFLOW_CONTRACT_REF_MISSING",
                )

    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_key: str) -> None:
        if node_key in visited:
            return
        if node_key in visiting:
            raise WorkflowDefinitionError(
                "workflow graph contains a dependency cycle",
                code="WORKFLOW_DEPENDENCY_CYCLE",
            )
        visiting.add(node_key)
        for dependency in node_by_key[node_key].dependencies:
            visit(dependency)
        visiting.remove(node_key)
        visited.add(node_key)
        ordered.append(node_key)

    for node in graph.nodes:
        visit(node.node_key)
    _validate_entrypoint_groups(graph.nodes)
    return tuple(ordered)


def _validate_entrypoint_groups(nodes: tuple[WorkflowNodeDefinition, ...]) -> None:
    groups: dict[tuple[str, str], list[WorkflowNodeDefinition]] = defaultdict(list)
    for node in nodes:
        # Scope/branch compatibility is checked by validate_workflow_graph before
        # this function is called; keeping the guard here makes the index builder
        # fail closed when it is used directly by another loader.
        if not isinstance(node.branch_key, str):
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has no concrete branch key",
                code="WORKFLOW_NODE_BRANCH_INVALID",
            )
        groups[(node.execution_scope, node.branch_key)].append(node)
    for (scope, branch), members in groups.items():
        entries = [node.node_key for node in members if node.entrypoint]
        if len(entries) != 1:
            raise WorkflowDefinitionError(
                f"workflow group {scope}/{branch} must have exactly one entrypoint; "
                f"found {entries}",
                code="WORKFLOW_ENTRYPOINT_GROUP_INVALID",
            )


def build_workflow_indexes(graph: WorkflowGraph) -> WorkflowIndexes:
    """Build branch-scoped producers and ContentDefinition reverse entries.

    The indexes are derived from the immutable binding snapshot. They are not a
    second source of truth and never infer a producer from artifact_type or a
    business node name.
    """

    # Keep direct callers fail-closed as well as registry callers.  The registry
    # already performs this validation before invoking the builder, so this is a
    # cheap no-op on the normal publication path.
    validate_workflow_graph(graph)
    producers: dict[str, list[WorkflowProducerRef]] = defaultdict(list)
    scoped: dict[tuple[str, str, str], WorkflowProducerRef] = {}
    for node in graph.nodes:
        if not isinstance(node.branch_key, str):
            raise WorkflowDefinitionError(
                f"workflow node {node.node_key} has no concrete branch key",
                code="WORKFLOW_NODE_BRANCH_INVALID",
            )
        producer = WorkflowProducerRef(
            node_key=node.node_key,
            execution_scope=node.execution_scope,
            branch_key=node.branch_key,
            output_contract_refs=tuple(node.output_contract_refs),
        )
        for contract_ref in node.output_contract_refs:
            scoped_key = (node.execution_scope, node.branch_key, contract_ref)
            if scoped_key in scoped:
                previous = scoped[scoped_key]
                raise WorkflowDefinitionError(
                    f"contract {contract_ref} has multiple producers in "
                    f"{node.execution_scope}/{node.branch_key}: "
                    f"{previous.node_key}, {node.node_key}",
                    code="WORKFLOW_OUTPUT_PRODUCER_DUPLICATE",
                )
            scoped[scoped_key] = producer
            producers[contract_ref].append(producer)

    output_entries: dict[str, WorkflowOutputDefinitionBinding] = {}
    for node in graph.nodes:
        if node.execution_kind != "model_generation":
            continue
        binding = _mapping(node.binding)
        if binding is None:
            raise WorkflowDefinitionError(
                f"model node {node.node_key} has an invalid binding",
                code="WORKFLOW_OUTPUT_INDEX_INVALID",
            )
        persistence = _mapping(binding.get("output_persistence"))
        if persistence is None:
            raise WorkflowDefinitionError(
                f"model node {node.node_key} has no output persistence",
                code="WORKFLOW_OUTPUT_INDEX_INVALID",
            )
        artifact = _mapping(persistence.get("artifact"))
        if artifact is None:
            raise WorkflowDefinitionError(
                f"model node {node.node_key} has an invalid output persistence",
                code="WORKFLOW_OUTPUT_INDEX_INVALID",
            )
        content_ref = _mapping(artifact.get("content_definition_ref"))
        generation_ref = _mapping(binding.get("generation_template_ref"))
        if content_ref is None:
            raise WorkflowDefinitionError(
                f"model node {node.node_key} has an invalid content definition ref",
                code="WORKFLOW_OUTPUT_INDEX_INVALID",
            )
        if len(node.output_contract_refs) != 1:
            raise WorkflowDefinitionError(
                f"model node {node.node_key} must map output persistence to exactly one contract",
                code="WORKFLOW_OUTPUT_CONTRACT_AMBIGUOUS",
            )
        if generation_ref is None or generation_ref.get("kind") != "generation_template":
            raise WorkflowDefinitionError(
                f"model node {node.node_key} has an invalid generation template ref",
                code="WORKFLOW_OUTPUT_INDEX_INVALID",
            )
        content_key = _text(content_ref, "item_key")
        generation_key = _text(generation_ref, "item_key")
        if content_ref.get("kind") != "content_definition":
            raise WorkflowDefinitionError(
                f"output definition kind is invalid for {node.node_key}",
                code="WORKFLOW_OUTPUT_INDEX_INVALID",
            )
        if content_key in output_entries:
            previous = output_entries[content_key]
            raise WorkflowDefinitionError(
                f"content definition {content_key} has multiple producers: "
                f"{previous.producer_node_key}, {node.node_key}",
                code="WORKFLOW_OUTPUT_DEFINITION_DUPLICATE",
            )
        quality = _resolve_quality_binding(node, graph.nodes)
        output_entries[content_key] = WorkflowOutputDefinitionBinding(
            content_definition_key=content_key,
            generation_template_key=generation_key,
            producer_node_key=node.node_key,
            execution_scope=node.execution_scope,
            producer_branch_key=_text_value(node.branch_key, "branch_key"),
            artifact_branch_key=_text(artifact, "branch_key"),
            artifact_type=_text(artifact, "artifact_type"),
            output_contract_refs=tuple(node.output_contract_refs),
            quality_validate_node_key=quality[0],
            quality_report_refs=quality[1],
            quality_validator_refs=quality[2],
            quality_gate_node_key=quality[3],
            quality_requirement_mode=quality[4],
        )

    producer_values = {
        key: tuple(
            sorted(
                values,
                key=lambda item: (item.execution_scope, item.branch_key, item.node_key),
            )
        )
        for key, values in producers.items()
    }
    scoped_values = {
        key: scoped[key]
        for key in sorted(scoped, key=lambda item: (item[0], item[1], item[2]))
    }
    output_values = {key: output_entries[key] for key in sorted(output_entries)}
    return WorkflowIndexes(
        producers_by_contract=MappingProxyType(producer_values),
        producer_index=MappingProxyType(scoped_values),
        output_definition_index=MappingProxyType(output_values),
    )


def _resolve_quality_binding(
    producer: WorkflowNodeDefinition,
    nodes: tuple[WorkflowNodeDefinition, ...],
) -> tuple[
    str | None,
    tuple[str, ...],
    tuple[tuple[str, str, str], ...],
    str | None,
    str,
]:
    candidates: list[tuple[WorkflowNodeDefinition, Mapping[str, Any]]] = []
    for node in nodes:
        if (
            node.execution_kind != "deterministic"
            or node.execution_scope != producer.execution_scope
            or node.branch_key != producer.branch_key
            or producer.node_key not in node.dependencies
        ):
            continue
        node_binding = _mapping(node.binding)
        quality = _mapping(
            node_binding.get("quality_report_persistence") if node_binding is not None else None
        )
        if quality is None:
            continue
        source_ref = quality.get("source_input_ref")
        if source_ref in producer.output_contract_refs:
            candidates.append((node, quality))
    if len(candidates) > 1:
        raise WorkflowDefinitionError(
            f"content definition producer {producer.node_key} has ambiguous quality validators",
            code="WORKFLOW_OUTPUT_QUALITY_AMBIGUOUS",
        )

    direct_gates = [
        node
        for node in nodes
        if (
            node.execution_kind == "human_gate"
            and node.execution_scope == producer.execution_scope
            and node.branch_key == producer.branch_key
            and producer.node_key in node.dependencies
        )
    ]
    if len(direct_gates) > 1:
        raise WorkflowDefinitionError(
            f"content definition producer {producer.node_key} has ambiguous quality gates",
            code="WORKFLOW_OUTPUT_QUALITY_AMBIGUOUS",
        )

    if candidates:
        validate_node, quality = candidates[0]
        report_ref = _text(quality, "report_ref")
        report_refs = (report_ref,)
        validator_refs = tuple(
            _descriptor_identity(ref)
            for ref in _sequence(quality.get("validator_refs"), "validator_refs")
        )
        gate = direct_gates[0] if direct_gates else None
        if gate is None:
            raise WorkflowDefinitionError(
                f"quality report {report_ref} has no human gate for {producer.node_key}",
                code="WORKFLOW_OUTPUT_QUALITY_GATE_MISSING",
            )
        gate_binding = _mapping(gate.binding)
        requirement = _mapping(
            gate_binding.get("quality_requirement") if gate_binding is not None else None
        )
        if requirement is None or requirement.get("mode") != "reports":
            raise WorkflowDefinitionError(
                f"quality gate {gate.node_key} does not require the declared report",
                code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
            )
        gate_reports = tuple(
            _text_value(item, "report_ref")
            for item in _sequence(requirement.get("report_refs"), "report_refs")
        )
        if len(gate_reports) != len(set(gate_reports)):
            raise WorkflowDefinitionError(
                f"quality gate {gate.node_key} contains duplicate report refs",
                code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
            )
        if set(gate_reports) != set(report_refs):
            raise WorkflowDefinitionError(
                f"quality gate {gate.node_key} has a different report set",
                code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
            )
        return (
            validate_node.node_key,
            report_refs,
            validator_refs,
            gate.node_key,
            "reports",
        )

    gate = direct_gates[0] if direct_gates else None
    if gate is None:
        return (None, (), (), None, "none")
    gate_binding = _mapping(gate.binding)
    requirement = _mapping(
        gate_binding.get("quality_requirement") if gate_binding is not None else None
    )
    if requirement is None:
        raise WorkflowDefinitionError(
            f"quality gate {gate.node_key} has no quality requirement",
            code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
        )
    mode = _text(requirement, "mode")
    if mode == "reports":
        raise WorkflowDefinitionError(
            f"quality gate {gate.node_key} has no deterministic report producer",
            code="WORKFLOW_OUTPUT_QUALITY_GATE_INVALID",
        )
    return (None, (), (), gate.node_key, mode)


def _mapping(value: object) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    entries = cast(Mapping[object, object], value)
    if any(type(key) is not str for key in entries):
        return None
    return cast(Mapping[str, Any], value)


def _sequence(value: object, field: str) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise WorkflowDefinitionError(
            f"workflow output index field {field} must be an array",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return tuple(cast(Sequence[object], value))


def _text(value: Mapping[str, Any] | None, field: str) -> str:
    if value is None:
        raise WorkflowDefinitionError(
            f"workflow output index field {field} is missing",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return _text_value(value.get(field), field)


def _text_value(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise WorkflowDefinitionError(
            f"workflow output index field {field} is invalid",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return value


def _descriptor_identity(value: object) -> tuple[str, str, str]:
    mapping = _mapping(value)
    if mapping is None:
        raise WorkflowDefinitionError(
            "workflow output index validator descriptor is invalid",
            code="WORKFLOW_OUTPUT_INDEX_INVALID",
        )
    return (
        _text(mapping, "key"),
        _text(mapping, "semantic_version"),
        _text(mapping, "implementation_digest"),
    )
