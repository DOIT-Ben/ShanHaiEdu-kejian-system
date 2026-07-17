from __future__ import annotations

import pytest

from workflow.definition import (
    WorkflowDefinitionError,
    WorkflowGraph,
    WorkflowNodeDefinition,
    validate_workflow_graph,
)


def node(key: str, *dependencies: str) -> WorkflowNodeDefinition:
    return WorkflowNodeDefinition(
        node_key=key,
        branch_key="lesson_plan",
        dependencies=dependencies,
        input_contract_refs=(),
        output_contract_refs=(),
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
                branch_key="lesson_plan",
                dependencies=(),
                input_contract_refs=("content:missing",),
                output_contract_refs=(),
            ),
        )
    )

    with pytest.raises(WorkflowDefinitionError, match="contract refs"):
        validate_workflow_graph(
            graph,
            available_contract_refs=frozenset({"content:lesson_plan"}),
        )
