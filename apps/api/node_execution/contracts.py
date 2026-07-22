"""Internal contracts owned by the generic node execution transaction."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelAuditContext,
    TextModelRequest,
)
from apps.api.model_gateway.pending import PendingTextGeneration
from apps.api.model_gateway.ports import CancellationToken
from apps.api.runtime_boundary.ports import (
    ArtifactContextVersion,
    FrozenSnapshotRefs,
    ReferenceAssetAuthorization,
    RuntimeNodeDefinition,
    TargetSlotAuthorization,
    WorkflowExecutionContext,
)


class NodeExecutionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class NodeExecutionCommitContext:
    definition: RuntimeNodeDefinition
    execution: WorkflowExecutionContext
    snapshots: FrozenSnapshotRefs
    upstream_artifacts: dict[str, ArtifactContextVersion]
    runtime_values: dict[str, Any]
    target_slot_authorization: TargetSlotAuthorization | None = None
    reference_asset_authorization: ReferenceAssetAuthorization | None = None


@dataclass(frozen=True, slots=True)
class PreparedNodeExecution:
    node_run_id: UUID
    request: TextModelRequest
    audit_context: ModelAuditContext
    output_schema: dict[str, object]
    execution_owner_token: str | None = None
    pre_model_error_code: str | None = None
    pre_model_error_message: str | None = None
    commit_context: NodeExecutionCommitContext | None = None
    committed_result: CommittedNodeExecution | None = None
    recovery_available: bool = False


@dataclass(frozen=True, slots=True)
class CommittedNodeExecution:
    node_run_id: UUID
    artifact_version_id: UUID
    creation_package_id: UUID | None
    attempt_id: UUID | None = None
    usage_id: UUID | None = None


class NodeExecutionTransaction(Protocol):
    def prepare(
        self,
        node_run_id: UUID,
        request_id: str,
        user_revision: str | None = None,
    ) -> PreparedNodeExecution: ...

    def checkpoint(
        self,
        execution: PreparedNodeExecution,
        output: dict[str, Any],
        pending: PendingTextGeneration,
    ) -> None: ...

    def commit(self, execution: PreparedNodeExecution) -> CommittedNodeExecution: ...

    def terminalize_failure(
        self,
        execution: PreparedNodeExecution,
        *,
        code: str,
        cancelled: bool,
    ) -> None: ...


class NodeExecutionTransactionFactory(Protocol):
    def begin(self) -> AbstractContextManager[NodeExecutionTransaction]: ...


class NodeExecutionModelPort(Protocol):
    async def generate_text_pending(
        self,
        request: TextModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> PendingTextGeneration: ...

    def fail_text_pending(
        self,
        pending: PendingTextGeneration,
        *,
        code: GatewayErrorCode = GatewayErrorCode.INVALID_RESPONSE,
    ) -> None: ...
