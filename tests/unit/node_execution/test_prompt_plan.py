from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest

from apps.api.node_execution.prompt_plan import (
    NodePromptPlanError,
    compile_node_prompt,
)
from apps.api.runtime_boundary.ports import RuntimeNodeDefinition, WorkflowExecutionContext
from workflow.prompt_runtime import ContextItem

RELEASE_ID = UUID("10000000-0000-4000-8000-000000000001")
WORKFLOW_ID = UUID("10000000-0000-4000-8000-000000000002")
NODE_RUN_ID = UUID("10000000-0000-4000-8000-000000000003")
PROJECT_ID = UUID("10000000-0000-4000-8000-000000000004")
USER_ID = UUID("10000000-0000-4000-8000-000000000005")

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary"],
    "properties": {"summary": {"type": "string"}},
}


def definition() -> RuntimeNodeDefinition:
    return RuntimeNodeDefinition(
        content_release_id=RELEASE_ID,
        workflow_definition_version_id=WORKFLOW_ID,
        node_key="example.generate",
        execution_kind="model_generation",
        generation_template_key="example.generate",
        generation_template={
            "kind": "generation_template",
            "metadata": {"key": "example.generate"},
            "spec": {
                "template_key": "example.generate",
                "model_capability": "text.structured.zh_primary_math",
                "prompt_template_ref": {
                    "item_key": "example.generate.prompt",
                    "kind": "prompt_template",
                },
                "output_definition_ref": {
                    "item_key": "example.generate.output",
                    "kind": "content_definition",
                },
            },
        },
        node_binding={
            "node_key": "example.generate",
            "execution_kind": "model_generation",
            "execution_scope": "project",
            "branch_key": "project",
            "model_capability": "text.structured.zh_primary_math",
            "generation_template_ref": {
                "item_key": "example.generate",
                "kind": "generation_template",
            },
            "context_policy": {
                "mode": "declared",
                "allowed_sources": ["source.approved_version"],
                "forbidden_sources": [],
            },
            "output_persistence": {"artifact": {}},
        },
        content_definition_version_id=UUID("10000000-0000-4000-8000-000000000006"),
        content_definition_release_id=RELEASE_ID,
        content_definition_item_key="example.generate.output",
    )


def execution() -> WorkflowExecutionContext:
    return WorkflowExecutionContext(
        organization_id=UUID("10000000-0000-4000-8000-000000000007"),
        project_id=PROJECT_ID,
        workflow_run_id=UUID("10000000-0000-4000-8000-000000000008"),
        node_run_id=NODE_RUN_ID,
        content_release_id=RELEASE_ID,
        workflow_definition_version_id=WORKFLOW_ID,
        node_key="example.generate",
        branch_key="project",
        lesson_key=None,
        lesson_unit_id=None,
        status="ready",
    )


def prompt_template() -> dict[str, object]:
    return {
        "kind": "prompt_template",
        "metadata": {"key": "example.generate.prompt"},
        "spec": {
            "template_key": "example.generate.prompt",
            "model_capability": "text.structured.zh_primary_math",
            "output_definition_ref": {
                "item_key": "example.generate.output",
                "kind": "content_definition",
            },
            "sections": [
                {
                    "section_key": "task",
                    "layer": "task",
                    "content": "Generate the published output.",
                    "editable": True,
                    "visible_to_teacher": True,
                }
            ],
            "context_bindings": [
                {
                    "binding_key": "approved_source",
                    "source": "source.approved_version",
                    "required": True,
                    "exposure": "full",
                    "max_items": 1,
                    "max_bytes": 1000,
                }
            ],
            "user_edit_policy": {
                "mode": "replace_editable_layer",
                "max_chars": 1000,
            },
        },
    }


def context_item(source: str = "source.approved_version") -> ContextItem:
    return ContextItem(
        source=source,
        source_id="source-id",
        source_version_id="source-version-id",
        content={"approved": True},
    )


def test_compiles_hidden_schema_and_declared_context_into_one_request() -> None:
    plan = compile_node_prompt(
        definition=definition(),
        execution=execution(),
        prompt_template=prompt_template(),
        output_schema=OUTPUT_SCHEMA,
        context_items=(context_item(),),
        request_id="node-execution:example",
        user_id=USER_ID,
    )

    assert plan.request.capability.value == "text.structured.zh_primary_math"
    assert plan.request.prompt == plan.prompt.compiled_prompt
    assert plan.prompt.request_schema == OUTPUT_SCHEMA
    assert plan.prompt.preview.editable_prompt == (
        'Generate the published output.\n\n{"context":[{"approved":true}]}'
    )
    assert plan.audit_context.node_run_id == NODE_RUN_ID
    assert plan.context.bindings[0]["source"] == "source.approved_version"


def test_rejects_context_not_declared_by_the_published_policy() -> None:
    with pytest.raises(NodePromptPlanError) as caught:
        compile_node_prompt(
            definition=definition(),
            execution=execution(),
            prompt_template=prompt_template(),
            output_schema=OUTPUT_SCHEMA,
            context_items=(context_item("other.source"),),
            request_id="node-execution:example",
            user_id=USER_ID,
        )

    assert caught.value.code == "NODE_EXECUTION_CONTEXT_POLICY_MISMATCH"


def test_rejects_capability_or_output_contract_drift() -> None:
    current = definition()
    template = dict(current.generation_template)
    spec = dict(template["spec"])
    spec["model_capability"] = "text.structured.ppt_design"
    template["spec"] = spec

    with pytest.raises(NodePromptPlanError) as caught:
        compile_node_prompt(
            definition=replace(current, generation_template=template),
            execution=execution(),
            prompt_template=prompt_template(),
            output_schema=OUTPUT_SCHEMA,
            context_items=(context_item(),),
            request_id="node-execution:example",
            user_id=USER_ID,
        )

    assert caught.value.code == "NODE_EXECUTION_PROMPT_CONTRACT_MISMATCH"
