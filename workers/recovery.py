"""Periodic worker recovery across attempt leases and private Runtime facts."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from apps.api.model_gateway.attempt_recovery import AttemptRecoveryCoordinator
from apps.api.node_execution.retention import RecoveryFactRetentionCoordinator


@dataclass(frozen=True, slots=True)
class WorkerRecoveryResult:
    cancellation_requests: int
    recovered_attempts: int
    expired_recovery_facts: int


class WorkerRecoveryCoordinator:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._attempts = AttemptRecoveryCoordinator(session_factory)
        self._facts = RecoveryFactRetentionCoordinator(session_factory)

    def reconcile(self, *, limit: int = 100) -> WorkerRecoveryResult:
        attempts = self._attempts.reconcile(limit=limit)
        return WorkerRecoveryResult(
            cancellation_requests=attempts.cancellation_requests,
            recovered_attempts=attempts.recovered,
            expired_recovery_facts=self._facts.cleanup_expired(limit=limit),
        )
