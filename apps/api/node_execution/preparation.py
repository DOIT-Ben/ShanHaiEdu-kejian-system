"""Pure assembly of a frozen node-execution command."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.api.content_runtime.runtime_port import RuntimeNodeMaterials
from apps.api.model_gateway.execution_port import SucceededAttempt
from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    FrozenSnapshotRefs,
    ReferenceAssetAuthorization,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)

from .contracts import NodeExecutionCommitContext, PreparedNodeExecution
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
