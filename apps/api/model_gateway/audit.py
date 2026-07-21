"""Provider-independent persistent attempt and usage audit sink."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apps.api.database import database_wall_clock
from apps.api.ids import new_uuid7
from apps.api.jobs.service import (
    GenerationJobAttemptBindingReader,
    GenerationJobBinding,
    GenerationJobCancellationReader,
)
from apps.api.model_gateway.audit_contracts import (
    AttemptCompletion,
    AttemptHeartbeat,
    AttemptLease,
    AttemptRequestAudit,
    AttemptSuccessAudit,
    DuplicateAttemptDelivery,
)
from apps.api.model_gateway.audit_models import (
    GenerationAttempt,
    GenerationAttemptCounter,
    UsageRecord,
)
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelAuditContext,
    ModelGatewayError,
    ModelUsage,
)
from apps.api.workflows.models import NodeRun, WorkflowRun


class SqlAlchemyAttemptAuditSink:
    """Write each audit transition in its own short database transaction."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        lease_seconds: int = 60,
    ) -> None:
        if lease_seconds < 1:
            raise ValueError("attempt lease must be at least one second")
        self._session_factory = session_factory
        self._lease_seconds = lease_seconds

    def start(
        self,
        context: ModelAuditContext,
        request: AttemptRequestAudit,
        *,
        provider_name: str | None,
        provider_model: str | None,
        route_reason: str,
    ) -> AttemptLease:
        try:
            with self._session_factory() as session, session.begin():
                self._lock_context_node(session, context)
                self._require_generation_job_binding(session, context)
                self._reject_duplicate_delivery(session, context, request)
                attempt_no = self._allocate_attempt_no(session, context.node_run_id)
                now = database_wall_clock(session)
                lease_owner = str(new_uuid7())
                attempt = GenerationAttempt(
                    id=new_uuid7(),
                    organization_id=context.organization_id,
                    project_id=context.project_id,
                    node_run_id=context.node_run_id,
                    generation_job_id=context.generation_job_id,
                    attempt_no=attempt_no,
                    request_id=request.request_id,
                    capability=request.capability,
                    operation_kind=request.operation_kind,
                    provider_name=provider_name,
                    provider_model=provider_model,
                    route_reason=route_reason,
                    status="running",
                    request_hash=request.request_hash,
                    provider_request_id=None,
                    provider_task_id=None,
                    lease_owner=lease_owner,
                    lease_expires_at=now + timedelta(seconds=self._lease_seconds),
                    heartbeat_at=now,
                    cancel_requested_at=None,
                    submitted_at=now,
                    error_details_json={},
                )
                session.add(attempt)
                session.flush()
                return AttemptLease(attempt_id=attempt.id, lease_owner=lease_owner)
        except IntegrityError as exc:
            if _constraint_name(exc) == "uq_generation_attempts_organization_request":
                raise DuplicateAttemptDelivery("model request delivery already exists") from None
            raise

    @staticmethod
    def _lock_context_node(session: Session, context: ModelAuditContext) -> None:
        node = session.scalar(
            select(NodeRun)
            .join(WorkflowRun, WorkflowRun.id == NodeRun.workflow_run_id)
            .where(
                NodeRun.id == context.node_run_id,
                NodeRun.organization_id == context.organization_id,
                WorkflowRun.project_id == context.project_id,
            )
            .with_for_update(of=NodeRun)
        )
        if node is None:
            raise RuntimeError("model audit context does not match the target node")

    @staticmethod
    def _require_generation_job_binding(session: Session, context: ModelAuditContext) -> None:
        if context.generation_job_id is None:
            return
        GenerationJobAttemptBindingReader(session).require_bindable(
            GenerationJobBinding(
                generation_job_id=context.generation_job_id,
                organization_id=context.organization_id,
                project_id=context.project_id,
            )
        )

    @staticmethod
    def _reject_duplicate_delivery(
        session: Session,
        context: ModelAuditContext,
        request: AttemptRequestAudit,
    ) -> None:
        duplicate = session.scalar(
            select(GenerationAttempt.id).where(
                GenerationAttempt.organization_id == context.organization_id,
                GenerationAttempt.request_id == request.request_id,
            )
        )
        if duplicate is not None:
            raise DuplicateAttemptDelivery("model request delivery already exists")

    def heartbeat(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
    ) -> AttemptHeartbeat:
        with self._session_factory() as session, session.begin():
            attempt = self._find_owned_running(session, lease, context)
            if attempt is None:
                return AttemptHeartbeat.LOST
            if attempt.cancel_requested_at is not None or self._job_cancel_requested(
                session, attempt
            ):
                attempt.cancel_requested_at = attempt.cancel_requested_at or database_wall_clock(
                    session
                )
                return AttemptHeartbeat.CANCEL_REQUESTED
            now = database_wall_clock(session)
            attempt.heartbeat_at = now
            attempt.lease_expires_at = now + timedelta(seconds=self._lease_seconds)
            return AttemptHeartbeat.ACTIVE

    def succeed(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
        result: AttemptSuccessAudit,
        *,
        latency_ms: int,
    ) -> AttemptCompletion:
        with self._session_factory() as session, session.begin():
            attempt = self._require_owned_running(session, lease, context)
            now = database_wall_clock(session)
            outcome = (
                AttemptCompletion.CANCELLED
                if attempt.cancel_requested_at is not None
                or self._job_cancel_requested(session, attempt)
                else AttemptCompletion.SUCCEEDED
            )
            if outcome == AttemptCompletion.CANCELLED:
                attempt.cancel_requested_at = attempt.cancel_requested_at or now
            attempt.status = outcome.value
            attempt.provider_request_id = _bounded(result.provider_request_id, 255)
            attempt.provider_task_id = _bounded(result.provider_task_id, 255)
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
            session.add(
                self._usage_record(
                    attempt,
                    context,
                    input_units=_input_units(result.usage),
                    output_units=_output_units(result.usage),
                    actual_cost=result.usage.cost,
                    currency=result.usage.currency,
                    latency_ms=latency_ms,
                    provider_model=_bounded(result.actual_model, 160),
                )
            )
            return outcome

    def fail(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
        error: ModelGatewayError,
        *,
        latency_ms: int,
    ) -> None:
        with self._session_factory() as session, session.begin():
            attempt = self._require_owned_running(session, lease, context)
            job_cancelled = self._job_cancel_requested(session, attempt)
            if job_cancelled and attempt.cancel_requested_at is None:
                attempt.cancel_requested_at = database_wall_clock(session)
            attempt.status = (
                "cancelled"
                if attempt.cancel_requested_at is not None or job_cancelled
                else {
                    "MODEL_CANCELLED": "cancelled",
                    "MODEL_SUBMISSION_UNKNOWN": "submission_unknown",
                }.get(error.code.value, "failed")
            )
            attempt.finished_at = database_wall_clock(session)
            attempt.error_code = (
                GatewayErrorCode.CANCELLED.value
                if attempt.status == "cancelled"
                else error.code.value
            )
            attempt.error_details_json = {
                "retryable": False if attempt.status == "cancelled" else error.retryable,
                "retry_after_seconds": (
                    None if attempt.status == "cancelled" else error.retry_after_seconds
                ),
            }
            attempt.latency_ms = latency_ms
            attempt.lease_owner = None
            attempt.lease_expires_at = None
            session.add(
                self._usage_record(
                    attempt,
                    context,
                    input_units={"prompt_tokens": 0},
                    output_units={"completion_tokens": 0, "total_tokens": 0},
                    actual_cost=None,
                    currency="USD",
                    latency_ms=latency_ms,
                    provider_model=attempt.provider_model,
                )
            )

    @staticmethod
    def _require_owned_running(
        session: Session,
        lease: AttemptLease,
        context: ModelAuditContext,
    ) -> GenerationAttempt:
        attempt = SqlAlchemyAttemptAuditSink._find_owned_running(session, lease, context)
        if attempt is None:
            raise RuntimeError("model audit attempt lease is missing, lost, or already terminal")
        return attempt

    @staticmethod
    def _find_owned_running(
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
        database_now = database_wall_clock(session)
        if attempt.lease_expires_at is None or attempt.lease_expires_at < database_now:
            return None
        return attempt

    @staticmethod
    def _job_cancel_requested(session: Session, attempt: GenerationAttempt) -> bool:
        if attempt.generation_job_id is None:
            return False
        binding = GenerationJobBinding(
            generation_job_id=attempt.generation_job_id,
            organization_id=attempt.organization_id,
            project_id=attempt.project_id,
        )
        return binding in GenerationJobCancellationReader(session).requested_bindings({binding})

    @staticmethod
    def _allocate_attempt_no(session: Session, node_run_id: UUID) -> int:
        statement = (
            insert(GenerationAttemptCounter)
            .values(node_run_id=node_run_id, next_attempt_no=2)
            .on_conflict_do_update(
                index_elements=[GenerationAttemptCounter.node_run_id],
                set_={
                    "next_attempt_no": GenerationAttemptCounter.next_attempt_no + 1,
                },
            )
            .returning(GenerationAttemptCounter.next_attempt_no)
        )
        next_attempt_no = session.scalar(statement)
        if next_attempt_no is None:
            raise RuntimeError("model attempt number allocation failed")
        return next_attempt_no - 1

    @staticmethod
    def _usage_record(
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


def model_request_hash(request: BaseModel) -> str:
    payload = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bounded(value: str | None, limit: int) -> str | None:
    return value[:limit] if value is not None else None


def _input_units(usage: ModelUsage) -> dict[str, int]:
    units = dict(usage.input_units)
    units["prompt_tokens"] = usage.prompt_tokens
    return units


def _output_units(usage: ModelUsage) -> dict[str, int]:
    units = dict(usage.output_units)
    units["completion_tokens"] = usage.completion_tokens
    units["total_tokens"] = usage.total_tokens
    return units


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)
