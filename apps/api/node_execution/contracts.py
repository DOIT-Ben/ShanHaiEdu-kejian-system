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


class NodeExecutionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class PreparedNodeExecution:
    node_run_id: UUID
    request: TextModelRequest
    audit_context: ModelAuditContext
    output_schema: dict[str, object]


@dataclass(frozen=True, slots=True)
class CommittedNodeExecution:
    node_run_id: UUID
    artifact_version_id: UUID
    creation_package_id: UUID | None


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
