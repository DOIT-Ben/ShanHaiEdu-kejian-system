"""Attempt and zero-cost usage facts for trusted deterministic executors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from apps.api.database import database_wall_clock
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.model_gateway.audit_models import (
    GenerationAttempt,
    GenerationAttemptCounter,
    UsageRecord,
)
from apps.api.model_gateway.execution_port import AttemptEvidence
from apps.api.runtime_boundary.ports import WorkflowExecutionContext

_LEASE_SECONDS = 300


class DeterministicAttemptError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DeterministicAttemptLease:
    attempt_id: UUID
    lease_owner: str
    request_id: str


class SqlAlchemyDeterministicAttemptPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def start(
        self,
        execution: WorkflowExecutionContext,
        *,
        owner_token: str,
        request_hash: str,
        capability: str,
    ) -> DeterministicAttemptLease:
        self._expire_stale(execution)
        active = self._session.scalar(
            select(GenerationAttempt.id).where(
                GenerationAttempt.organization_id == self._actor.organization_id,
                GenerationAttempt.node_run_id == execution.node_run_id,
                GenerationAttempt.status == "running",
            )
        )
        if active is not None:
            raise _error(
                "PPT_RUNTIME_IN_FLIGHT",
                "another deterministic attempt is still active",
            )
        attempt_no = self._allocate_attempt_no(execution.node_run_id)
        request_id = f"ppt-runtime:{execution.node_run_id}:{attempt_no}"
        now = database_wall_clock(self._session)
        attempt = GenerationAttempt(
            id=new_uuid7(),
            organization_id=execution.organization_id,
            project_id=execution.project_id,
            node_run_id=execution.node_run_id,
            generation_job_id=None,
            attempt_no=attempt_no,
            request_id=request_id,
            capability=capability,
            operation_kind="deterministic_execute",
            provider_name=None,
            provider_model=None,
            route_reason="deterministic_runtime",
            status="running",
            request_hash=request_hash,
            provider_request_id=None,
            provider_task_id=None,
            lease_owner=owner_token,
            lease_expires_at=now + timedelta(seconds=_LEASE_SECONDS),
            heartbeat_at=now,
            cancel_requested_at=None,
            submitted_at=now,
            finished_at=None,
            error_code=None,
            error_details_json={},
            latency_ms=None,
        )
        self._session.add(attempt)
        self._session.flush()
        return DeterministicAttemptLease(
            attempt_id=attempt.id,
            lease_owner=owner_token,
            request_id=request_id,
        )

    def complete(
        self,
        execution: WorkflowExecutionContext,
        lease: DeterministicAttemptLease,
        *,
        latency_ms: int,
        input_bytes: int,
        output_bytes: int,
    ) -> AttemptEvidence:
        attempt = self._require_owned_running(execution, lease, require_unexpired=True)
        attempt.status = "succeeded"
        attempt.finished_at = database_wall_clock(self._session)
        attempt.latency_ms = max(0, latency_ms)
        attempt.lease_owner = None
        attempt.lease_expires_at = None
        usage = self._usage(
            attempt,
            input_units={"input_bytes": max(0, input_bytes)},
            output_units={"output_bytes": max(0, output_bytes)},
            latency_ms=max(0, latency_ms),
        )
        self._session.add(usage)
        self._session.flush()
        return AttemptEvidence(
            attempt_id=attempt.id,
            usage_id=usage.id,
            attempt_no=attempt.attempt_no,
        )

    def fail_if_owned(
        self,
        execution: WorkflowExecutionContext,
        lease: DeterministicAttemptLease,
        *,
        code: str,
        cancelled: bool,
        latency_ms: int,
    ) -> bool:
        attempt = self._owned_running(execution, lease)
        if attempt is None:
            return False
        attempt.status = "cancelled" if cancelled else "failed"
        attempt.finished_at = database_wall_clock(self._session)
        attempt.error_code = code[:160]
        attempt.error_details_json = {"retryable": False}
        attempt.latency_ms = max(0, latency_ms)
        attempt.lease_owner = None
        attempt.lease_expires_at = None
        self._session.add(
            self._usage(
                attempt,
                input_units={"input_bytes": 0},
                output_units={"output_bytes": 0},
                latency_ms=max(0, latency_ms),
            )
        )
        self._session.flush()
        return True

    def succeeded(self, execution: WorkflowExecutionContext) -> AttemptEvidence:
        attempt = self._session.scalar(
            select(GenerationAttempt)
            .where(
                GenerationAttempt.organization_id == self._actor.organization_id,
                GenerationAttempt.project_id == execution.project_id,
                GenerationAttempt.node_run_id == execution.node_run_id,
                GenerationAttempt.operation_kind == "deterministic_execute",
                GenerationAttempt.status == "succeeded",
            )
            .order_by(GenerationAttempt.attempt_no.desc())
        )
        if attempt is None:
            raise _error(
                "PPT_RUNTIME_ATTEMPT_NOT_SUCCEEDED",
                "the deterministic node has no successful attempt",
            )
        usage = self._session.scalar(
            select(UsageRecord).where(
                UsageRecord.organization_id == self._actor.organization_id,
                UsageRecord.generation_attempt_id == attempt.id,
            )
        )
        if usage is None:
            raise _error(
                "PPT_RUNTIME_USAGE_MISSING",
                "the deterministic attempt has no usage record",
            )
        return AttemptEvidence(attempt.id, usage.id, attempt.attempt_no)

    def _expire_stale(self, execution: WorkflowExecutionContext) -> None:
        now = database_wall_clock(self._session)
        rows = list(
            self._session.scalars(
                select(GenerationAttempt)
                .where(
                    GenerationAttempt.organization_id == self._actor.organization_id,
                    GenerationAttempt.project_id == execution.project_id,
                    GenerationAttempt.node_run_id == execution.node_run_id,
                    GenerationAttempt.operation_kind == "deterministic_execute",
                    GenerationAttempt.status == "running",
                    GenerationAttempt.lease_expires_at <= now,
                )
                .with_for_update()
            )
        )
        for attempt in rows:
            attempt.status = "failed"
            attempt.finished_at = now
            attempt.error_code = "PPT_RUNTIME_ATTEMPT_EXPIRED"
            attempt.error_details_json = {"retryable": True}
            attempt.latency_ms = 0
            attempt.lease_owner = None
            attempt.lease_expires_at = None
            self._session.add(
                self._usage(
                    attempt,
                    input_units={"input_bytes": 0},
                    output_units={"output_bytes": 0},
                    latency_ms=0,
                )
            )
        if rows:
            self._session.flush()

    def _require_owned_running(
        self,
        execution: WorkflowExecutionContext,
        lease: DeterministicAttemptLease,
        *,
        require_unexpired: bool,
    ) -> GenerationAttempt:
        attempt = self._owned_running(execution, lease)
        if attempt is None:
            raise _error(
                "PPT_RUNTIME_ATTEMPT_OWNER_LOST",
                "the deterministic attempt lease is missing or lost",
            )
        if require_unexpired:
            now = database_wall_clock(self._session)
            if attempt.lease_expires_at is None or attempt.lease_expires_at < now:
                raise _error(
                    "PPT_RUNTIME_ATTEMPT_OWNER_LOST",
                    "the deterministic attempt lease expired before commit",
                )
        return attempt

    def _owned_running(
        self,
        execution: WorkflowExecutionContext,
        lease: DeterministicAttemptLease,
    ) -> GenerationAttempt | None:
        return self._session.scalar(
            select(GenerationAttempt)
            .where(
                GenerationAttempt.id == lease.attempt_id,
                GenerationAttempt.organization_id == self._actor.organization_id,
                GenerationAttempt.project_id == execution.project_id,
                GenerationAttempt.node_run_id == execution.node_run_id,
                GenerationAttempt.operation_kind == "deterministic_execute",
                GenerationAttempt.request_id == lease.request_id,
                GenerationAttempt.status == "running",
                GenerationAttempt.lease_owner == lease.lease_owner,
            )
            .with_for_update()
        )

    def _allocate_attempt_no(self, node_run_id: UUID) -> int:
        statement = (
            insert(GenerationAttemptCounter)
            .values(node_run_id=node_run_id, next_attempt_no=2)
            .on_conflict_do_update(
                index_elements=[GenerationAttemptCounter.node_run_id],
                set_={"next_attempt_no": GenerationAttemptCounter.next_attempt_no + 1},
            )
            .returning(GenerationAttemptCounter.next_attempt_no)
        )
        next_attempt_no = self._session.scalar(statement)
        if next_attempt_no is None:
            raise _error(
                "PPT_RUNTIME_ATTEMPT_ALLOCATION_FAILED",
                "the deterministic attempt number could not be allocated",
            )
        return int(next_attempt_no) - 1

    def _usage(
        self,
        attempt: GenerationAttempt,
        *,
        input_units: dict[str, int],
        output_units: dict[str, int],
        latency_ms: int,
    ) -> UsageRecord:
        return UsageRecord(
            id=new_uuid7(),
            organization_id=attempt.organization_id,
            user_id=self._actor.user_id,
            project_id=attempt.project_id,
            node_run_id=attempt.node_run_id,
            generation_attempt_id=attempt.id,
            capability=attempt.capability,
            provider_name=None,
            provider_model=None,
            input_units_json=input_units,
            output_units_json=output_units,
            pricing_version="deterministic-zero-cost/v1",
            estimated_cost=Decimal("0"),
            actual_cost=Decimal("0"),
            currency="USD",
            latency_ms=latency_ms,
        )


def _error(code: str, message: str) -> DeterministicAttemptError:
    return DeterministicAttemptError(code, message)
