"""Caller-owned transaction helpers for Attempt success and Usage."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.database import database_wall_clock
from apps.api.ids import new_uuid7
from apps.api.jobs.service import GenerationJobBinding, GenerationJobCancellationReader
from apps.api.model_gateway.audit_contracts import (
    AttemptCompletion,
    AttemptLease,
    AttemptSuccessAudit,
)
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import GatewayErrorCode, ModelAuditContext


def complete_attempt_success(
    session: Session,
    lease: AttemptLease,
    context: ModelAuditContext,
    result: AttemptSuccessAudit,
    *,
    latency_ms: int,
) -> tuple[AttemptCompletion, UUID]:
    attempt = require_owned_running(session, lease, context)
    now = database_wall_clock(session)
    outcome = (
        AttemptCompletion.CANCELLED
        if attempt.cancel_requested_at is not None or job_cancel_requested(session, attempt)
        else AttemptCompletion.SUCCEEDED
    )
    if outcome == AttemptCompletion.CANCELLED:
        attempt.cancel_requested_at = attempt.cancel_requested_at or now
    attempt.status = outcome.value
    attempt.provider_request_id = bounded(result.provider_request_id, 255)
    attempt.provider_task_id = bounded(result.provider_task_id, 255)
    attempt.finished_at = now
    attempt.latency_ms = latency_ms
    attempt.lease_owner = None
    attempt.lease_expires_at = None
    if outcome == AttemptCompletion.CANCELLED:
        attempt.error_code = GatewayErrorCode.CANCELLED.value
        attempt.error_details_json = {
            "retryable": False,
            "retry_after_seconds": None,
        }
    usage = build_usage_record(
        attempt,
        context,
        input_units={**result.usage.input_units, "prompt_tokens": result.usage.prompt_tokens},
        output_units={
            **result.usage.output_units,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
        },
        actual_cost=result.usage.cost,
        currency=result.usage.currency,
        latency_ms=latency_ms,
        provider_model=bounded(result.actual_model, 160),
    )
    session.add(usage)
    session.flush()
    return outcome, usage.id


def require_owned_running(
    session: Session,
    lease: AttemptLease,
    context: ModelAuditContext,
) -> GenerationAttempt:
    attempt = find_owned_running(session, lease, context)
    if attempt is None:
        raise RuntimeError("model audit attempt lease is missing, lost, or already terminal")
    return attempt


def find_owned_running(
    session: Session,
    lease: AttemptLease,
    context: ModelAuditContext,
) -> GenerationAttempt | None:
    attempt = session.scalar(
        select(GenerationAttempt)
        .where(
            GenerationAttempt.id == lease.attempt_id,
            GenerationAttempt.organization_id == context.organization_id,
            GenerationAttempt.project_id == context.project_id,
            GenerationAttempt.node_run_id == context.node_run_id,
            GenerationAttempt.status == "running",
            GenerationAttempt.lease_owner == lease.lease_owner,
        )
        .with_for_update()
    )
    if attempt is None:
        return None
    now = database_wall_clock(session)
    if attempt.lease_expires_at is None or attempt.lease_expires_at < now:
        return None
    return attempt


def job_cancel_requested(session: Session, attempt: GenerationAttempt) -> bool:
    if attempt.generation_job_id is None:
        return False
    binding = GenerationJobBinding(
        generation_job_id=attempt.generation_job_id,
        organization_id=attempt.organization_id,
        project_id=attempt.project_id,
    )
    return binding in GenerationJobCancellationReader(session).requested_bindings({binding})


def build_usage_record(
    attempt: GenerationAttempt,
    context: ModelAuditContext,
    *,
    input_units: dict[str, int],
    output_units: dict[str, int],
    actual_cost: Decimal | None,
    currency: str,
    latency_ms: int,
    provider_model: str | None,
) -> UsageRecord:
    return UsageRecord(
        id=new_uuid7(),
        organization_id=context.organization_id,
        user_id=context.user_id,
        project_id=context.project_id,
        node_run_id=context.node_run_id,
        generation_attempt_id=attempt.id,
        capability=attempt.capability,
        provider_name=attempt.provider_name,
        provider_model=provider_model,
        input_units_json=input_units,
        output_units_json=output_units,
        pricing_version=None,
        estimated_cost=None,
        actual_cost=actual_cost,
        currency=currency.upper()[:3],
        latency_ms=latency_ms,
    )


def bounded(value: str | None, limit: int) -> str | None:
    return value[:limit] if value is not None else None
