from __future__ import annotations

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


def test_valid_workflow_graph_returns_dependency_order() -> None:
    graph = WorkflowGraph(nodes=(node("prepare"), node("generate", "prepare")))

    assert validate_workflow_graph(graph) == ("prepare", "generate")


@pytest.mark.parametrize(
    ("graph", "message"),
    (
        (WorkflowGraph(nodes=(node("same"), node("same"))), "duplicate"),
        (WorkflowGraph(nodes=(node("generate", "missing"),)), "missing"),
        (
            WorkflowGraph(nodes=(node("first", "second"), node("second", "first"))),
            "cycle",
        ),
    ),
)
def test_invalid_workflow_graph_is_rejected_before_publication(
    graph: WorkflowGraph,
    message: str,
) -> None:
    with pytest.raises(WorkflowDefinitionError, match=message):
        validate_workflow_graph(graph)


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

    with pytest.raises(WorkflowDefinitionError, match="entrypoint"):
        validate_workflow_graph(WorkflowGraph(nodes=(*dependencies, invalid)))


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
