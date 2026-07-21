"""Private result handle for callers that atomically checkpoint validated text."""

from __future__ import annotations

from dataclasses import dataclass

from apps.api.model_gateway.audit_contracts import AttemptLease, AttemptSuccessAudit
from apps.api.model_gateway.contracts import ModelAuditContext, TextGatewayResult


@dataclass(frozen=True, slots=True)
class PendingTextGeneration:
    result: TextGatewayResult
    lease: AttemptLease | None
    audit_context: ModelAuditContext | None
    success_audit: AttemptSuccessAudit
