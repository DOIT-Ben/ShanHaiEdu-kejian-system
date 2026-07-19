"""Lease expiry and cancellation coordination for generation attempts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.ids import new_uuid7
from apps.api.jobs.service import GenerationJobBinding, GenerationJobCancellationReader
from apps.api.model_gateway.audit import database_wall_clock
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord

_MAX_POSTGRES_INTEGER = 2_147_483_647


@dataclass(frozen=True, slots=True)
class AttemptRecoveryResult:
    cancellation_requests: int
    cancelled: int
    failed: int
    submission_unknown: int

    @property
    def recovered(self) -> int:
        return self.cancelled + self.failed + self.submission_unknown


@dataclass(frozen=True, slots=True)
class _CancellationCursor:
    submitted_at: datetime
    attempt_id: UUID


class AttemptRecoveryCoordinator:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._cancellation_cursor: _CancellationCursor | None = None
        self._reconcile_lock = Lock()

    def reconcile(self, *, limit: int = 100) -> AttemptRecoveryResult:
        if limit < 1:
            raise ValueError("attempt recovery limit must be positive")
        with self._reconcile_lock:
            with self._session_factory() as session, session.begin():
                cancellation_requests, next_cursor = self._coordinate_job_cancellations(
                    session,
                    limit=limit,
                    cursor=self._cancellation_cursor,
                )
                recovered = self._recover_expired(session, limit=limit)
            self._cancellation_cursor = next_cursor
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
            attempt.cancel_requested_at = attempt.cancel_requested_at or database_wall_clock(
                session
            )
            return True

    @classmethod
    def _coordinate_job_cancellations(
        cls,
        session: Session,
        *,
        limit: int,
        cursor: _CancellationCursor | None,
    ) -> tuple[int, _CancellationCursor | None]:
        attempts = cls._load_cancellation_candidates(session, limit=limit, cursor=cursor)
        if not attempts and cursor is not None:
            attempts = cls._load_cancellation_candidates(session, limit=limit, cursor=None)
        if not attempts:
            return 0, None
        bindings_by_attempt = {
            attempt.id: GenerationJobBinding(
                generation_job_id=generation_job_id,
                organization_id=attempt.organization_id,
                project_id=attempt.project_id,
            )
            for attempt in attempts
            if (generation_job_id := attempt.generation_job_id) is not None
        }
        cancelled_bindings = GenerationJobCancellationReader(session).requested_bindings(
            set(bindings_by_attempt.values())
        )
        if not cancelled_bindings:
            return 0, _CancellationCursor(attempts[-1].submitted_at, attempts[-1].id)
        now = database_wall_clock(session)
        coordinated = 0
        for attempt in attempts:
            if bindings_by_attempt.get(attempt.id) in cancelled_bindings:
                attempt.cancel_requested_at = now
                coordinated += 1
        return coordinated, _CancellationCursor(attempts[-1].submitted_at, attempts[-1].id)

    @staticmethod
    def _load_cancellation_candidates(
        session: Session,
        *,
        limit: int,
        cursor: _CancellationCursor | None,
    ) -> list[GenerationAttempt]:
        statement = select(GenerationAttempt).where(
            GenerationAttempt.status == "running",
            GenerationAttempt.cancel_requested_at.is_(None),
            GenerationAttempt.generation_job_id.is_not(None),
        )
        if cursor is not None:
            statement = statement.where(
                or_(
                    GenerationAttempt.submitted_at > cursor.submitted_at,
                    and_(
                        GenerationAttempt.submitted_at == cursor.submitted_at,
                        GenerationAttempt.id > cursor.attempt_id,
                    ),
                )
            )
        return list(
            session.scalars(
                statement.order_by(GenerationAttempt.submitted_at, GenerationAttempt.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )

    @staticmethod
    def _recover_expired(session: Session, *, limit: int) -> list[str]:
        now = database_wall_clock(session)
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
        attempt_ids = [attempt.id for attempt in attempts]
        existing_usage_attempt_ids: set[UUID] = (
            set(
                session.scalars(
                    select(UsageRecord.generation_attempt_id).where(
                        UsageRecord.generation_attempt_id.in_(attempt_ids)
                    )
                )
            )
            if attempt_ids
            else set()
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
            attempt.latency_ms = min(
                max(round((now - attempt.submitted_at).total_seconds() * 1_000), 0),
                _MAX_POSTGRES_INTEGER,
            )
            attempt.lease_owner = None
            attempt.lease_expires_at = None
            if attempt.id not in existing_usage_attempt_ids:
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
