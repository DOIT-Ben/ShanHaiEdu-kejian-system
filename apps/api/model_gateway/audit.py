"""Provider-independent persistent attempt and usage audit sink."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from apps.api.database import utc_now
from apps.api.ids import new_uuid7
from apps.api.model_gateway.audit_models import (
    GenerationAttempt,
    GenerationAttemptCounter,
    UsageRecord,
)
from apps.api.model_gateway.contracts import (
    ModelAuditContext,
    ModelGatewayError,
    ModelUsage,
)
from apps.api.workflows.models import NodeRun, WorkflowRun


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
    ) -> None: ...

    def fail(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
        error: ModelGatewayError,
        *,
        latency_ms: int,
    ) -> None: ...


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


class DuplicateAttemptDelivery(RuntimeError):
    """The same organization request has already created an attempt."""


@dataclass(frozen=True, slots=True)
class AttemptSuccessAudit:
    provider_request_id: str | None
    actual_model: str
    finish_reason: str | None
    usage: ModelUsage
    provider_task_id: str | None = None


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
        with self._session_factory() as session, session.begin():
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
            duplicate = session.scalar(
                select(GenerationAttempt.id).where(
                    GenerationAttempt.organization_id == context.organization_id,
                    GenerationAttempt.request_id == request.request_id,
                )
            )
            if duplicate is not None:
                raise DuplicateAttemptDelivery("model request delivery already exists")
            attempt_no = self._allocate_attempt_no(session, context.node_run_id)
            now = utc_now()
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

    def heartbeat(
        self,
        lease: AttemptLease,
        context: ModelAuditContext,
    ) -> AttemptHeartbeat:
        with self._session_factory() as session, session.begin():
            attempt = self._find_owned_running(session, lease, context)
            if attempt is None:
                return AttemptHeartbeat.LOST
            if attempt.cancel_requested_at is not None:
                return AttemptHeartbeat.CANCEL_REQUESTED
            now = utc_now()
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
    ) -> None:
        with self._session_factory() as session, session.begin():
            attempt = self._require_owned_running(session, lease, context)
            attempt.status = "succeeded"
            attempt.provider_request_id = _bounded(result.provider_request_id, 255)
            attempt.provider_task_id = _bounded(result.provider_task_id, 255)
            attempt.finished_at = utc_now()
            attempt.latency_ms = latency_ms
            attempt.lease_owner = None
            attempt.lease_expires_at = None
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
            attempt.status = {
                "MODEL_CANCELLED": "cancelled",
                "MODEL_SUBMISSION_UNKNOWN": "submission_unknown",
            }.get(error.code.value, "failed")
            attempt.finished_at = utc_now()
            attempt.error_code = error.code.value
            attempt.error_details_json = {
                "retryable": error.retryable,
                "retry_after_seconds": error.retry_after_seconds,
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
        return session.scalar(
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
