"""Pure assembly of a frozen node-execution command."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from apps.api.content_runtime.runtime_port import RuntimeNodeMaterials
from apps.api.model_gateway.contracts import ModelAuditContext, TextModelRequest
from apps.api.model_gateway.execution_port import SucceededAttempt
from apps.api.runtime_boundary.creation_package_contracts import (
    CreationPackageReferenceAssetSpec,
)
from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    FrozenSnapshotRefs,
    ReferenceAssetAuthorization,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)

from .contracts import NodeExecutionCommitContext, NodeExecutionError, PreparedNodeExecution
from .prompt_plan import CompiledNodePrompt


def build_prepared_execution(
    *,
    node_run_id: UUID,
    execution: WorkflowExecutionContext,
    materials: RuntimeNodeMaterials,
    compiled: CompiledNodePrompt,
    snapshots: FrozenSnapshotRefs,
    upstream: dict[str, ArtifactContextVersion],
    runtime_values: dict[str, Any],
    target_authorization: TargetSlotAuthorization | None,
    reference_authorization: ReferenceAssetAuthorization | None,
    succeeded: SucceededAttempt | None,
    recovery_state: str,
    owner_token: str,
) -> PreparedNodeExecution:
    return PreparedNodeExecution(
        node_run_id=node_run_id,
        request=compiled.request,
        audit_context=compiled.audit_context,
        output_schema=materials.output_schema,
        execution_owner_token=owner_token,
        pre_model_error_code=_recovery_error(succeeded, recovery_state),
        pre_model_error_message=(
            "the successful model result was lost before T2" if succeeded is not None else None
        ),
        commit_context=NodeExecutionCommitContext(
            definition=materials.definition,
            execution=execution,
            snapshots=snapshots,
            upstream_artifacts=upstream,
            runtime_values=runtime_values,
            target_slot_authorization=target_authorization,
            reference_asset_authorization=reference_authorization,
        ),
        recovery_available=recovery_state == "available",
    )


def _recovery_error(succeeded: SucceededAttempt | None, recovery_state: str) -> str | None:
    if succeeded is None or recovery_state == "available":
        return None
    if recovery_state == "expired":
        return "NODE_EXECUTION_RECOVERY_EXPIRED"
    return "NODE_EXECUTION_RESULT_UNAVAILABLE"


def build_recovered_execution(
    *,
    node_run_id: UUID,
    request: TextModelRequest,
    audit_context: ModelAuditContext,
    output_schema: dict[str, Any],
    commit_context: NodeExecutionCommitContext | None,
    succeeded: SucceededAttempt,
    recovery_state: str,
    owner_token: str,
) -> PreparedNodeExecution:
    return PreparedNodeExecution(
        node_run_id=node_run_id,
        request=request,
        audit_context=audit_context,
        output_schema=output_schema,
        execution_owner_token=owner_token,
        pre_model_error_code=_recovery_error(succeeded, recovery_state),
        pre_model_error_message="the successful model result is unavailable for T2",
        commit_context=commit_context,
        recovery_available=recovery_state == "available",
    )


def build_frozen_invocation(
    *,
    node_run_id: UUID,
    request: TextModelRequest,
    audit_context: ModelAuditContext,
    output_schema: dict[str, Any],
    commit_context: NodeExecutionCommitContext,
    owner_token: str,
) -> PreparedNodeExecution:
    return PreparedNodeExecution(
        node_run_id=node_run_id,
        request=request,
        audit_context=audit_context,
        output_schema=output_schema,
        execution_owner_token=owner_token,
        commit_context=commit_context,
    )


def frozen_model_request(frozen: Mapping[str, Any]) -> TextModelRequest:
    raw = frozen.get("model_request")
    if not isinstance(raw, Mapping):
        raise NodeExecutionError(
            "NODE_EXECUTION_FROZEN_INPUT_INVALID",
            "the frozen model request is invalid",
        )
    try:
        return TextModelRequest.model_validate(dict(cast(Mapping[str, object], raw)))
    except (TypeError, ValueError) as exc:
        raise NodeExecutionError(
            "NODE_EXECUTION_FROZEN_INPUT_INVALID",
            "the frozen model request is invalid",
        ) from exc


def recover_commit_context(
    *,
    materials: RuntimeNodeMaterials,
    execution: WorkflowExecutionContext,
    snapshots: FrozenSnapshotRefs,
    upstream: dict[str, ArtifactContextVersion],
    frozen: Mapping[str, Any],
) -> NodeExecutionCommitContext:
    _validate_frozen_identity(execution, snapshots, frozen)
    target_slots = _string_sequence(frozen.get("target_slots"), "target slots")
    reference_assets = _reference_assets(frozen.get("reference_assets"))
    reference_authorized = frozen.get("reference_assets_authorized")
    if type(reference_authorized) is not bool:
        raise NodeExecutionError(
            "NODE_EXECUTION_FROZEN_INPUT_INVALID",
            "the reference-asset authorization marker is invalid",
        )
    target_authorization, reference_authorization = _recover_authorizations(
        execution,
        target_slots,
        reference_assets,
        reference_authorized,
    )
    return NodeExecutionCommitContext(
        definition=materials.definition,
        execution=execution,
        snapshots=snapshots,
        upstream_artifacts=upstream,
        runtime_values=(
            {
                "reference_assets": [
                    {"asset_version_id": str(asset.asset_version_id), "role": asset.role}
                    for asset in reference_assets
                ]
            }
            if reference_authorized
            else {}
        ),
        target_slot_authorization=target_authorization,
        reference_asset_authorization=reference_authorization,
    )


def _validate_frozen_identity(
    execution: WorkflowExecutionContext,
    snapshots: FrozenSnapshotRefs,
    frozen: Mapping[str, Any],
) -> None:
    if (
        frozen.get("content_release_id") != str(execution.content_release_id)
        or frozen.get("workflow_definition_version_id")
        != str(execution.workflow_definition_version_id)
        or frozen.get("node_key") != execution.node_key
        or frozen.get("context_hash") != snapshots.context_hash
        or frozen.get("prompt_hash") != snapshots.prompt_hash
    ):
        raise NodeExecutionError(
            "NODE_EXECUTION_FROZEN_INPUT_INVALID",
            "the frozen execution identity or snapshots are invalid",
        )


def _recover_authorizations(
    execution: WorkflowExecutionContext,
    target_slots: tuple[str, ...],
    reference_assets: tuple[CreationPackageReferenceAssetSpec, ...],
    reference_authorized: bool,
) -> tuple[TargetSlotAuthorization | None, ReferenceAssetAuthorization | None]:
    branch_key = execution.branch_key
    if branch_key is None:
        raise NodeExecutionError(
            "NODE_EXECUTION_FROZEN_INPUT_INVALID",
            "the frozen execution branch is unavailable",
        )
    target_authorization = (
        TargetSlotAuthorization(
            content_release_id=execution.content_release_id,
            workflow_definition_version_id=execution.workflow_definition_version_id,
            project_id=execution.project_id,
            node_key=execution.node_key,
            branch_key=branch_key,
            lesson_unit_id=execution.lesson_unit_id,
            slots=target_slots,
        )
        if target_slots
        else None
    )
    reference_authorization = (
        ReferenceAssetAuthorization(
            content_release_id=execution.content_release_id,
            workflow_definition_version_id=execution.workflow_definition_version_id,
            project_id=execution.project_id,
            node_key=execution.node_key,
            branch_key=branch_key,
            lesson_unit_id=execution.lesson_unit_id,
            assets=reference_assets,
        )
        if reference_authorized
        else None
    )
    return target_authorization, reference_authorization


def frozen_upstream_refs(frozen: Mapping[str, Any]) -> dict[str, UUID]:
    raw = frozen.get("upstream_artifacts")
    if not isinstance(raw, Mapping):
        raise NodeExecutionError(
            "NODE_EXECUTION_FROZEN_INPUT_INVALID",
            "the frozen upstream artifact map is invalid",
        )
    values: dict[str, UUID] = {}
    for key, value in cast(Mapping[object, object], raw).items():
        if type(key) is not str:
            raise NodeExecutionError(
                "NODE_EXECUTION_FROZEN_INPUT_INVALID",
                "a frozen upstream artifact key is invalid",
            )
        try:
            values[key] = UUID(str(value))
        except ValueError as exc:
            raise NodeExecutionError(
                "NODE_EXECUTION_FROZEN_INPUT_INVALID",
                "a frozen upstream artifact version is invalid",
            ) from exc
    return values


def _string_sequence(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise NodeExecutionError(
            "NODE_EXECUTION_FROZEN_INPUT_INVALID",
            f"the frozen {label} are invalid",
        )
    values = tuple(cast(Sequence[object], value))
    if any(type(item) is not str or not item for item in values):
        raise NodeExecutionError(
            "NODE_EXECUTION_FROZEN_INPUT_INVALID",
            f"the frozen {label} are invalid",
        )
    return cast(tuple[str, ...], values)


def _reference_assets(value: object) -> tuple[CreationPackageReferenceAssetSpec, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise NodeExecutionError(
            "NODE_EXECUTION_FROZEN_INPUT_INVALID",
            "the frozen reference assets are invalid",
        )
    assets: list[CreationPackageReferenceAssetSpec] = []
    for raw in cast(Sequence[object], value):
        if not isinstance(raw, Mapping):
            raise NodeExecutionError(
                "NODE_EXECUTION_FROZEN_INPUT_INVALID",
                "a frozen reference asset is invalid",
            )
        item = cast(Mapping[str, object], raw)
        try:
            assets.append(
                CreationPackageReferenceAssetSpec(
                    asset_version_id=UUID(str(item["asset_version_id"])),
                    role=str(item["role"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise NodeExecutionError(
                "NODE_EXECUTION_FROZEN_INPUT_INVALID",
                "a frozen reference asset is invalid",
            ) from exc
    return tuple(assets)
