"""Provider-independent attempt audit port and lifecycle value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from apps.api.model_gateway.contracts import ModelAuditContext, ModelGatewayError, ModelUsage


@dataclass(frozen=True, slots=True)
class AttemptRequestAudit:
    request_id: str
    capability: str
    request_hash: str
    operation_kind: str


@dataclass(frozen=True, slots=True)
class AttemptLease:
    attempt_id: UUID
    lease_owner: str


class AttemptHeartbeat(StrEnum):
    ACTIVE = "active"
    CANCEL_REQUESTED = "cancel_requested"
    LOST = "lost"


class AttemptCompletion(StrEnum):
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"


class DuplicateAttemptDelivery(RuntimeError):
    """The same organization request has already created an attempt."""


@dataclass(frozen=True, slots=True)
class AttemptSuccessAudit:
    provider_request_id: str | None
    actual_model: str
    finish_reason: str | None
    usage: ModelUsage
    provider_task_id: str | None = None


class AttemptAuditSink(Protocol):
    def start(
        self,
        context: ModelAuditContext,
        request: AttemptRequestAudit,
        *,
        provider_name: str | None,
        provider_model: str | None,
        route_reason: str,
    ) -> AttemptLease: ...

    def heartbeat(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
    ) -> AttemptHeartbeat: ...

    def succeed(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
        result: AttemptSuccessAudit,
        *,
        latency_ms: int,
    ) -> AttemptCompletion: ...

    def fail(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
        error: ModelGatewayError,
        *,
        latency_ms: int,
        result: AttemptSuccessAudit | None = None,
    ) -> None: ...
