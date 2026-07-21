"""Pure assembly helpers for frozen runtime input materials."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from apps.api.model_gateway.contracts import ModelAuditContext, ModelCapability, TextModelRequest
from apps.api.runtime_boundary.contract_values import plain_json_value
from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    ArtifactPort,
    AssetContextItem,
    AssetPort,
    FrozenSnapshotRefs,
    WorkflowExecutionContext,
)
from workflow.prompt_runtime import ContextItem

from .contracts import NodeExecutionError
from .prompt_plan import CompiledNodePrompt


def collect_context_items(
    artifacts: ArtifactPort,
    assets: AssetPort,
    execution: WorkflowExecutionContext,
    binding: Mapping[str, Any],
) -> tuple[ContextItem, ...]:
    raw_policy = binding.get("context_policy")
    if not isinstance(raw_policy, Mapping):
        raise NodeExecutionError(
            "NODE_EXECUTION_CONTEXT_POLICY_INVALID",
            "the published context policy is invalid",
        )
    policy = cast(Mapping[str, Any], raw_policy)
    allowed = policy.get("allowed_sources")
    if not isinstance(allowed, Sequence) or isinstance(allowed, (str, bytes, bytearray)):
        raise NodeExecutionError(
            "NODE_EXECUTION_CONTEXT_POLICY_INVALID",
            "the published context policy has no source allowlist",
        )
    items: list[ContextItem] = []
    for source in cast(Sequence[object], allowed):
        if type(source) is not str:
            raise NodeExecutionError(
                "NODE_EXECUTION_CONTEXT_POLICY_INVALID",
                "the published context source is invalid",
            )
        items.extend(
            ContextItem(
                source=source,
                source_id=str(value.artifact_version_id),
                source_version_id=str(value.artifact_version_id),
                content=cast(Mapping[str, Any], plain_json_value(value.content)),
            )
            for value in artifacts.list_context_versions(execution, source)
        )
        items.extend(
            _asset_context_item(source, value)
            for value in assets.list_context_items(execution.project_id, source)
        )
    return tuple(items)


def collect_upstream_artifacts(
    artifacts: ArtifactPort,
    execution: WorkflowExecutionContext,
    binding: Mapping[str, Any],
) -> dict[str, ArtifactContextVersion]:
    refs = binding.get("input_contract_refs")
    if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes, bytearray)):
        raise NodeExecutionError(
            "NODE_EXECUTION_INPUT_CONTRACT_INVALID",
            "the published input contract list is invalid",
        )
    upstream: dict[str, ArtifactContextVersion] = {}
    for raw in cast(Sequence[object], refs):
        if type(raw) is not str:
            continue
        values = artifacts.list_context_versions(execution, raw)
        if len(values) == 1:
            upstream[raw] = values[0]
    return upstream


def execution_snapshot(
    execution: WorkflowExecutionContext,
    compiled: CompiledNodePrompt,
    snapshots: FrozenSnapshotRefs,
    upstream: Mapping[str, ArtifactContextVersion],
    reference_assets: Sequence[Mapping[str, str]],
    *,
    target_slots: Sequence[str] = (),
    reference_assets_authorized: bool = False,
) -> dict[str, Any]:
    return {
        "content_release_id": str(execution.content_release_id),
        "workflow_definition_version_id": str(execution.workflow_definition_version_id),
        "node_key": execution.node_key,
        "context_hash": snapshots.context_hash,
        "prompt_hash": snapshots.prompt_hash,
        "model_request": compiled.request.model_dump(mode="json"),
        "context": list(compiled.context.bindings),
        "upstream_artifacts": {
            key: str(value.artifact_version_id) for key, value in upstream.items()
        },
        "reference_assets": list(reference_assets),
        "reference_assets_authorized": reference_assets_authorized,
        "target_slots": list(target_slots),
    }


def audit_context(execution: WorkflowExecutionContext, user_id: UUID | None) -> ModelAuditContext:
    return ModelAuditContext(
        organization_id=execution.organization_id,
        user_id=user_id,
        project_id=execution.project_id,
        node_run_id=execution.node_run_id,
        generation_job_id=None,
    )


def placeholder_request(request_id: str) -> TextModelRequest:
    return TextModelRequest(
        capability=ModelCapability.TEXT_SMOKE,
        request_id=f"node-execution:committed:{request_id}"[:160],
        prompt="committed node execution",
    )


def _asset_context_item(source: str, value: AssetContextItem) -> ContextItem:
    return ContextItem(
        source=source,
        source_id=str(value.source_id),
        source_version_id=str(value.source_version_id),
        content=value.facts,
    )
