from __future__ import annotations

import pytest

from workflow.definition import WorkflowDefinitionError
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY


def test_registry_loads_valid_graph_with_deterministic_order() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(
        {
            "nodes": [
                {
                    "node_key": "generate",
                    "branch_key": "lesson_plan",
                    "dependencies": ["prepare"],
                    "input_contract_refs": ["content:lesson_plan"],
                    "output_contract_refs": [],
                },
                {
                    "node_key": "prepare",
                    "branch_key": None,
                    "dependencies": [],
                    "input_contract_refs": [],
                    "output_contract_refs": ["content:lesson_plan"],
                },
            ]
        }
    )

    assert registered.topological_order == ("prepare", "generate")


@pytest.mark.parametrize(
    "payload",
    (
        {"nodes": [{"node_key": "same"}, {"node_key": "same"}]},
        {"nodes": [{"node_key": "generate", "dependencies": ["missing"]}]},
        {
            "nodes": [
                {
                    "node_key": "generate",
                    "input_contract_refs": ["content:missing"],
                }
            ]
        },
    ),
)
def test_registry_rejects_invalid_publication_payload(payload: dict[str, object]) -> None:
    with pytest.raises(WorkflowDefinitionError):
        BUILTIN_WORKFLOW_REGISTRY.load(payload)
