"""Internal contracts owned by the generic node execution transaction."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from apps.api.model_gateway.contracts import (
    ModelAuditContext,
    TextGatewayResult,
    TextModelRequest,
)
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


@dataclass(frozen=True, slots=True)
class CommittedNodeExecution:
    node_run_id: UUID
    artifact_version_id: UUID
    creation_package_id: UUID | None
    attempt_id: UUID | None = None
    usage_id: UUID | None = None


class NodeExecutionTransaction(Protocol):
    def prepare(self, node_run_id: UUID, request_id: str) -> PreparedNodeExecution: ...

    def commit(
        self,
        execution: PreparedNodeExecution,
        output: dict[str, Any],
        result: TextGatewayResult,
    ) -> CommittedNodeExecution: ...

    def terminalize_failure(
        self,
        execution: PreparedNodeExecution,
        *,
        code: str,
        cancelled: bool,
    ) -> None: ...


class NodeExecutionTransactionFactory(Protocol):
    def begin(self) -> AbstractContextManager[NodeExecutionTransaction]: ...
