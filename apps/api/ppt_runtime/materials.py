"""Frozen deterministic PPT input and execution identity helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from apps.api.assets.ppt_runtime_contracts import PptBackgroundFact
from apps.api.content_runtime.deterministic_port import DeterministicNodeDefinition
from apps.api.model_gateway.deterministic_port import DeterministicAttemptLease
from apps.api.runtime_boundary.ports import ArtifactContextVersion, WorkflowExecutionContext
from workflow.node_state import NodeStatus

from .contracts import PptRuntimeError, PreparedPptRuntime

SNAPSHOT_KIND = "shanhai.ppt-runtime/v1"
ASSEMBLE_EXECUTOR = "executor.ppt.pages_assemble"
EXPORT_EXECUTOR = "executor.ppt.pptx_export"


def build_prepared(
    definition: DeterministicNodeDefinition,
    execution: WorkflowExecutionContext,
    request_id: str,
    owner_token: str,
    attempt: DeterministicAttemptLease,
    inputs: Mapping[str, ArtifactContextVersion],
    backgrounds: tuple[PptBackgroundFact, ...],
) -> PreparedPptRuntime:
    page_specs = required_input(inputs, "artifact:ppt_page_specs")
    assembly = inputs.get("artifact:ppt_page_previews")
    return PreparedPptRuntime(
        definition=definition,
        execution=execution,
        request_id=request_id,
        owner_token=owner_token,
        attempt=attempt,
        upstream_artifacts=dict(inputs),
        page_spec_version_id=page_specs.artifact_version_id,
        page_spec_content=page_specs.content,
        backgrounds=backgrounds,
        assembly_artifact_version_id=(assembly.artifact_version_id if assembly else None),
        assembly_content=(assembly.content if assembly else None),
    )


def execution_snapshot(
    definition: DeterministicNodeDefinition,
    inputs: Mapping[str, ArtifactContextVersion],
    backgrounds: tuple[PptBackgroundFact, ...],
) -> dict[str, Any]:
    return {
        "kind": SNAPSHOT_KIND,
        "definition": definition_fact(definition),
        "artifacts": {
            ref: {
                "version_id": str(value.artifact_version_id),
                "content_hash": value.content_hash,
            }
            for ref, value in sorted(inputs.items())
        },
        "backgrounds": [item.snapshot() for item in backgrounds],
    }


def definition_fact(definition: DeterministicNodeDefinition) -> dict[str, str]:
    return {
        "content_release_id": str(definition.content_release_id),
        "workflow_definition_version_id": str(definition.workflow_definition_version_id),
        "node_key": definition.node_key,
        "executor_ref": definition.executor_ref,
        "content_definition_version_id": str(definition.content_definition_version_id),
        "content_definition_key": definition.content_definition_key,
    }


def require_supported_definition(
    definition: DeterministicNodeDefinition,
    execution: WorkflowExecutionContext,
) -> None:
    if (
        definition.executor_ref not in {ASSEMBLE_EXECUTOR, EXPORT_EXECUTOR}
        or definition.execution_scope != "lesson_unit"
        or definition.branch_key != "ppt"
        or definition.content_release_id != execution.content_release_id
        or definition.workflow_definition_version_id != execution.workflow_definition_version_id
        or definition.node_key != execution.node_key
    ):
        raise error(
            "PPT_RUNTIME_DEFINITION_INVALID",
            "the fixed deterministic definition cannot drive the PPT runtime",
        )


def require_commit_identity(
    prepared: PreparedPptRuntime,
    current: WorkflowExecutionContext,
) -> None:
    expected = prepared.execution
    if (
        current.organization_id != expected.organization_id
        or current.project_id != expected.project_id
        or current.workflow_run_id != expected.workflow_run_id
        or current.node_run_id != expected.node_run_id
        or current.content_release_id != expected.content_release_id
        or current.workflow_definition_version_id != expected.workflow_definition_version_id
        or current.node_key != expected.node_key
        or current.branch_key != expected.branch_key
        or current.lesson_unit_id != expected.lesson_unit_id
        or current.lesson_key != expected.lesson_key
        or current.status != NodeStatus.RUNNING.value
    ):
        raise error(
            "PPT_RUNTIME_EXECUTION_CHANGED",
            "the PPT node execution changed before result commit",
        )


def required_input(
    inputs: Mapping[str, ArtifactContextVersion],
    ref: str,
) -> ArtifactContextVersion:
    value = inputs.get(ref)
    if value is None:
        raise error(
            "PPT_RUNTIME_ARTIFACT_INPUT_INVALID",
            f"the exact deterministic artifact input is missing: {ref}",
        )
    return value


def mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise error("PPT_RUNTIME_FROZEN_INPUT_INVALID", "a frozen object is invalid")
    entries = cast(Mapping[object, object], value)
    if any(type(key) is not str for key in entries):
        raise error("PPT_RUNTIME_FROZEN_INPUT_INVALID", "a frozen object is invalid")
    return cast(Mapping[str, object], entries)


def sha256(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise error("PPT_RUNTIME_FROZEN_INPUT_INVALID", "a frozen hash is invalid")
    return value


def error(code: str, message: str) -> PptRuntimeError:
    return PptRuntimeError(code, message)
