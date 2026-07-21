from __future__ import annotations

from dataclasses import replace

import pytest

from workflow.definition import (
    WorkflowDefinitionError,
    WorkflowGraph,
    WorkflowNodeDefinition,
    build_workflow_indexes,
    validate_workflow_graph,
)


def node(
    key: str,
    *dependencies: str,
    execution_kind: str = "deterministic",
    scope: str = "lesson_unit",
    branch_key: str | None = "lesson_plan",
    entrypoint: bool | None = None,
) -> WorkflowNodeDefinition:
    return WorkflowNodeDefinition(
        node_key=key,
        execution_kind=execution_kind,
        execution_scope=scope,
        branch_key=branch_key,
        entrypoint=not dependencies if entrypoint is None else entrypoint,
        dependencies=dependencies,
        input_contract_refs=(),
        output_contract_refs=(),
        binding={},
    )


def model_node(
    key: str,
    *,
    cdef: str = "output.definition",
    contract: str = "artifact:output",
    branch_key: str = "lesson_plan",
) -> WorkflowNodeDefinition:
    return WorkflowNodeDefinition(
        node_key=key,
        execution_kind="model_generation",
        execution_scope="lesson_unit",
        branch_key=branch_key,
        entrypoint=True,
        dependencies=(),
        input_contract_refs=(),
        output_contract_refs=(contract,),
        binding={
            "generation_template_ref": {
                "kind": "generation_template",
                "item_key": f"{key}.template",
            },
            "output_persistence": {
                "artifact": {
                    "identity": {
                        "strategy": "lesson_unit_singleton",
                        "artifact_key_prefix": f"{key}-artifact",
                    },
                    "artifact_type": "test",
                    "branch_key": branch_key,
                    "content_definition_ref": {
                        "kind": "content_definition",
                        "item_key": cdef,
                    },
                }
            },
        },
    )


def quality_graph(
    *,
    gate_dependencies: tuple[str, ...] | None = ("generate", "validate"),
    validator_output_refs: tuple[str, ...] = ("report:quality",),
) -> WorkflowGraph:
    producer = model_node("generate")
    validator = WorkflowNodeDefinition(
        node_key="validate",
        execution_kind="deterministic",
        execution_scope="lesson_unit",
        branch_key="lesson_plan",
        entrypoint=False,
        dependencies=("generate",),
        input_contract_refs=("artifact:output",),
        output_contract_refs=validator_output_refs,
        binding={
            "quality_report_persistence": {
                "source_input_ref": "artifact:output",
                "report_ref": "report:quality",
                "validator_refs": [
                    {
                        "key": "validator.quality",
                        "semantic_version": "1.0.0",
                        "implementation_digest": "a" * 64,
                    }
                ],
            }
        },
    )
    if gate_dependencies is None:
        return WorkflowGraph(nodes=(producer, validator))
    gate = WorkflowNodeDefinition(
        node_key="approve",
        execution_kind="human_gate",
        execution_scope="lesson_unit",
        branch_key="lesson_plan",
        entrypoint=False,
        dependencies=gate_dependencies,
        input_contract_refs=("artifact:output", "report:quality"),
        output_contract_refs=("approval:quality",),
        binding={
            "quality_requirement": {
                "mode": "reports",
                "report_refs": ["report:quality"],
            }
        },
    )
    return WorkflowGraph(nodes=(producer, validator, gate))


def test_valid_workflow_graph_returns_dependency_order() -> None:
    graph = WorkflowGraph(nodes=(node("prepare"), node("generate", "prepare")))

    assert validate_workflow_graph(graph) == ("prepare", "generate")


def test_internal_input_producer_must_be_in_dependency_closure() -> None:
    start = node("start")
    producer = replace(
        node("producer", "start"),
        output_contract_refs=("artifact:source",),
    )
    parallel = node("parallel", "start")
    consumer = replace(
        node("consumer", "parallel"),
        input_contract_refs=("artifact:source",),
    )

    with pytest.raises(WorkflowDefinitionError) as caught:
        validate_workflow_graph(WorkflowGraph(nodes=(start, producer, parallel, consumer)))
    assert caught.value.code == "WORKFLOW_INPUT_DEPENDENCY_MISSING"

    ordered_consumer = replace(consumer, dependencies=("producer",))
    assert validate_workflow_graph(
        WorkflowGraph(nodes=(start, producer, parallel, ordered_consumer))
    ) == ("start", "producer", "parallel", "consumer")


def test_direct_quality_gate_must_consume_the_producer_output() -> None:
    producer = model_node("generate")
    gate = WorkflowNodeDefinition(
        node_key="approve",
        execution_kind="human_gate",
        execution_scope="lesson_unit",
        branch_key="lesson_plan",
        entrypoint=False,
        dependencies=("generate",),
        input_contract_refs=("approval:other",),
        output_contract_refs=("approval:quality",),
        binding={"quality_requirement": {"mode": "none"}},
    )

    with pytest.raises(WorkflowDefinitionError) as caught:
        build_workflow_indexes(WorkflowGraph(nodes=(producer, gate)))
    assert caught.value.code == "WORKFLOW_OUTPUT_QUALITY_GATE_INVALID"


@pytest.mark.parametrize(
    ("graph", "code"),
    (
        (
            WorkflowGraph(nodes=(node("same"), node("same"))),
            "WORKFLOW_NODE_KEY_DUPLICATE",
        ),
        (
            WorkflowGraph(nodes=(node("generate", "missing"),)),
            "WORKFLOW_DEPENDENCY_MISSING",
        ),
        (
            WorkflowGraph(nodes=(node("first", "second"), node("second", "first"))),
            "WORKFLOW_DEPENDENCY_CYCLE",
        ),
    ),
)
def test_invalid_workflow_graph_is_rejected_before_publication(
    graph: WorkflowGraph,
    code: str,
) -> None:
    with pytest.raises(WorkflowDefinitionError) as caught:
        validate_workflow_graph(graph)
    assert caught.value.code == code


def test_missing_contract_reference_is_rejected_before_publication() -> None:
    graph = WorkflowGraph(
        nodes=(
            WorkflowNodeDefinition(
                node_key="generate",
                execution_kind="deterministic",
                execution_scope="lesson_unit",
                branch_key="lesson_plan",
                entrypoint=True,
                dependencies=(),
                input_contract_refs=("content:missing",),
                output_contract_refs=(),
                binding={},
            ),
        )
    )

    with pytest.raises(WorkflowDefinitionError, match="contract refs"):
        validate_workflow_graph(
            graph,
            available_contract_refs=frozenset({"content:lesson_plan"}),
        )


@pytest.mark.parametrize(
    ("dependency", "message"),
    (
        (node("project", scope="project", branch_key="material"), "scope"),
        (node("intro", branch_key="intro_options"), "branch"),
    ),
)
def test_dependency_must_stay_in_one_execution_scope_and_branch(
    dependency: WorkflowNodeDefinition,
    message: str,
) -> None:
    graph = WorkflowGraph(
        nodes=(
            dependency,
            node("generate", dependency.node_key, entrypoint=False),
        )
    )

    with pytest.raises(WorkflowDefinitionError, match=message):
        validate_workflow_graph(graph)


@pytest.mark.parametrize(
    "invalid",
    (
        node("root", entrypoint=False),
        node("child", "root", entrypoint=True),
    ),
)
def test_entrypoint_declaration_must_match_dependencies(invalid: WorkflowNodeDefinition) -> None:
    dependencies = (node("root"),) if invalid.dependencies else ()

    with pytest.raises(WorkflowDefinitionError) as caught:
        validate_workflow_graph(WorkflowGraph(nodes=(*dependencies, invalid)))
    assert caught.value.code == "WORKFLOW_ENTRYPOINT_INVALID"


@pytest.mark.parametrize(
    "invalid",
    (
        node("project", scope="project", branch_key=None),
        node("project", scope="project", branch_key="lesson_plan"),
        node("lesson", branch_key=None),
        node("lesson", branch_key="material"),
    ),
)
def test_execution_scope_requires_an_explicit_compatible_branch(
    invalid: WorkflowNodeDefinition,
) -> None:
    with pytest.raises(WorkflowDefinitionError, match="branch") as caught:
        validate_workflow_graph(WorkflowGraph(nodes=(invalid,)))
    assert caught.value.code == "WORKFLOW_NODE_BRANCH_INVALID"


def test_each_scope_branch_group_requires_exactly_one_entrypoint() -> None:
    graph = WorkflowGraph(nodes=(node("first"), node("second")))

    with pytest.raises(WorkflowDefinitionError, match="exactly one entrypoint") as caught:
        validate_workflow_graph(graph)

    assert caught.value.code == "WORKFLOW_ENTRYPOINT_GROUP_INVALID"


def test_workflow_indexes_keep_cross_branch_contract_producers() -> None:
    graph = WorkflowGraph(
        nodes=(
            model_node(
                "ppt.image",
                cdef="ppt.image.output",
                contract="asset:image_candidates",
                branch_key="ppt",
            ),
            model_node(
                "video.image",
                cdef="video.image.output",
                contract="asset:image_candidates",
                branch_key="video",
            ),
        )
    )

    indexes = build_workflow_indexes(graph)

    assert [
        producer.node_key for producer in indexes.producers_by_contract["asset:image_candidates"]
    ] == ["ppt.image", "video.image"]


def test_workflow_indexes_reject_same_branch_contract_producers() -> None:
    first = model_node("first")
    second = model_node("second", cdef="second.output")
    second = WorkflowNodeDefinition(
        node_key=second.node_key,
        execution_kind=second.execution_kind,
        execution_scope=second.execution_scope,
        branch_key=second.branch_key,
        entrypoint=False,
        dependencies=("first",),
        input_contract_refs=second.input_contract_refs,
        output_contract_refs=first.output_contract_refs,
        binding=second.binding,
    )

    with pytest.raises(WorkflowDefinitionError) as caught:
        build_workflow_indexes(WorkflowGraph(nodes=(first, second)))

    assert caught.value.code == "WORKFLOW_OUTPUT_PRODUCER_DUPLICATE"


def test_quality_gate_must_depend_on_producer_and_validator() -> None:
    graph = quality_graph(gate_dependencies=("generate",))

    with pytest.raises(WorkflowDefinitionError) as caught:
        build_workflow_indexes(graph)

    assert caught.value.code == "WORKFLOW_OUTPUT_QUALITY_GATE_INVALID"


def test_invalid_quality_report_contract_precedes_missing_gate_error() -> None:
    graph = quality_graph(
        gate_dependencies=None,
        validator_output_refs=("report:different",),
    )

    with pytest.raises(WorkflowDefinitionError) as caught:
        build_workflow_indexes(graph)

    assert caught.value.code == "WORKFLOW_OUTPUT_QUALITY_INVALID"


def test_missing_quality_gate_has_stable_error_after_valid_report_chain() -> None:
    with pytest.raises(WorkflowDefinitionError) as caught:
        build_workflow_indexes(quality_graph(gate_dependencies=None))

    assert caught.value.code == "WORKFLOW_OUTPUT_QUALITY_GATE_MISSING"
