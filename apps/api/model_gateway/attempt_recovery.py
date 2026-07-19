"""Lease expiry and cancellation coordination for generation attempts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.database import utc_now
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord


@dataclass(frozen=True, slots=True)
class AttemptRecoveryResult:
    cancellation_requests: int
    cancelled: int
    failed: int
    submission_unknown: int

    @property
    def recovered(self) -> int:
        return self.cancelled + self.failed + self.submission_unknown


class AttemptRecoveryCoordinator:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def reconcile(self, *, limit: int = 100) -> AttemptRecoveryResult:
        if limit < 1:
            raise ValueError("attempt recovery limit must be positive")
        with self._session_factory() as session, session.begin():
            cancellation_requests = self._coordinate_job_cancellations(session, limit=limit)
            recovered = self._recover_expired(session, limit=limit)
        return AttemptRecoveryResult(
            cancellation_requests=cancellation_requests,
            cancelled=recovered.count("cancelled"),
            failed=recovered.count("failed"),
            submission_unknown=recovered.count("submission_unknown"),
        )

    def request_cancel(self, attempt_id: UUID) -> bool:
        with self._session_factory() as session, session.begin():
            attempt = session.scalar(
                select(GenerationAttempt)
                .where(
                    GenerationAttempt.id == attempt_id,
                    GenerationAttempt.status == "running",
                )
                .with_for_update()
            )
            if attempt is None:
                return False
            attempt.cancel_requested_at = attempt.cancel_requested_at or utc_now()
            return True

    @staticmethod
    def _coordinate_job_cancellations(session: Session, *, limit: int) -> int:
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .join(GenerationJob, GenerationJob.id == GenerationAttempt.generation_job_id)
                .where(
                    GenerationAttempt.status == "running",
                    GenerationAttempt.cancel_requested_at.is_(None),
                    (
                        (GenerationJob.status.in_(("cancel_requested", "cancelled")))
                        | (GenerationJob.cancel_requested_at.is_not(None))
                    ),
                )
                .order_by(GenerationAttempt.submitted_at, GenerationAttempt.id)
                .limit(limit)
                .with_for_update(skip_locked=True, of=GenerationAttempt)
            )
        )
        now = utc_now()
        for attempt in attempts:
            attempt.cancel_requested_at = now
        return len(attempts)

    @staticmethod
    def _recover_expired(session: Session, *, limit: int) -> list[str]:
        now = utc_now()
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .where(
                    GenerationAttempt.status == "running",
                    GenerationAttempt.lease_expires_at < now,
                )
                .order_by(GenerationAttempt.lease_expires_at, GenerationAttempt.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        terminal_statuses: list[str] = []
        for attempt in attempts:
            status, error_code, retryable = _recovery_disposition(attempt)
            attempt.status = status
            attempt.finished_at = now
            attempt.error_code = error_code
            attempt.error_details_json = {
                "retryable": retryable,
                "retry_after_seconds": None,
            }
            attempt.latency_ms = max(round((now - attempt.submitted_at).total_seconds() * 1_000), 0)
            attempt.lease_owner = None
            attempt.lease_expires_at = None
            session.add(_zero_usage_record(attempt))
            terminal_statuses.append(status)
        return terminal_statuses


def _recovery_disposition(attempt: GenerationAttempt) -> tuple[str, str, bool]:
    if attempt.cancel_requested_at is not None:
        return "cancelled", "MODEL_CANCELLED", False
    if attempt.operation_kind in {"video_submit", "legacy_unknown"}:
        return "submission_unknown", "MODEL_SUBMISSION_UNKNOWN", False
    if attempt.provider_task_id is not None:
        return "submission_unknown", "MODEL_SUBMISSION_UNKNOWN", False
    return "failed", "MODEL_ATTEMPT_LEASE_EXPIRED", True


def _zero_usage_record(attempt: GenerationAttempt) -> UsageRecord:
    return UsageRecord(
        id=new_uuid7(),
        organization_id=attempt.organization_id,
        user_id=None,
        project_id=attempt.project_id,
        node_run_id=attempt.node_run_id,
        generation_attempt_id=attempt.id,
        capability=attempt.capability,
        provider_name=attempt.provider_name,
        provider_model=attempt.provider_model,
        input_units_json={"prompt_tokens": 0},
        output_units_json={"completion_tokens": 0, "total_tokens": 0},
        pricing_version=None,
        estimated_cost=None,
        actual_cost=None,
        currency="USD",
        latency_ms=attempt.latency_ms or 0,
    )
