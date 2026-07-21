"""Read-only attempt/usage facts consumed by the node execution owner."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord


class AttemptExecutionPortError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AttemptEvidence:
    attempt_id: UUID
    usage_id: UUID
    attempt_no: int


@dataclass(frozen=True, slots=True)
class SucceededAttempt:
    request_id: str
    evidence: AttemptEvidence
    recovery_text: str | None


class SqlAlchemyAttemptExecutionPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def next_model_request_id(self, node_run_id: UUID) -> str:
        latest = self._session.scalar(
            select(func.max(GenerationAttempt.attempt_no)).where(
                GenerationAttempt.organization_id == self._actor.organization_id,
                GenerationAttempt.node_run_id == node_run_id,
            )
        )
        return f"node-execution:{node_run_id}:{int(latest or 0) + 1}"

    def status_for_request(self, node_run_id: UUID, request_id: str) -> str | None:
        return self._session.scalar(
            select(GenerationAttempt.status).where(
                GenerationAttempt.organization_id == self._actor.organization_id,
                GenerationAttempt.node_run_id == node_run_id,
                GenerationAttempt.request_id == request_id,
            )
        )

    def has_active_attempt(self, node_run_id: UUID) -> bool:
        return (
            self._session.scalar(
                select(GenerationAttempt.id).where(
                    GenerationAttempt.organization_id == self._actor.organization_id,
                    GenerationAttempt.node_run_id == node_run_id,
                    GenerationAttempt.status == "running",
                )
            )
            is not None
        )

    def succeeded_attempt(self, *, node_run_id: UUID, project_id: UUID) -> SucceededAttempt | None:
        attempt = self._session.scalar(
            select(GenerationAttempt)
            .where(
                GenerationAttempt.organization_id == self._actor.organization_id,
                GenerationAttempt.project_id == project_id,
                GenerationAttempt.node_run_id == node_run_id,
                GenerationAttempt.status == "succeeded",
            )
            .order_by(GenerationAttempt.attempt_no.desc())
        )
        if attempt is None:
            return None
        usage = self._session.scalar(
            select(UsageRecord).where(
                UsageRecord.organization_id == self._actor.organization_id,
                UsageRecord.project_id == project_id,
                UsageRecord.node_run_id == node_run_id,
                UsageRecord.generation_attempt_id == attempt.id,
            )
        )
        if usage is None:
            raise AttemptExecutionPortError(
                "NODE_EXECUTION_USAGE_MISSING",
                "a successful attempt has no usage record",
            )
        return SucceededAttempt(
            request_id=attempt.request_id,
            evidence=AttemptEvidence(
                attempt_id=attempt.id,
                usage_id=usage.id,
                attempt_no=attempt.attempt_no,
            ),
            recovery_text=_recovery_text(attempt.error_details_json),
        )

    def require_succeeded(
        self,
        *,
        node_run_id: UUID,
        project_id: UUID,
        request_id: str,
    ) -> AttemptEvidence:
        attempt = self._session.scalar(
            select(GenerationAttempt)
            .where(
                GenerationAttempt.organization_id == self._actor.organization_id,
                GenerationAttempt.project_id == project_id,
                GenerationAttempt.node_run_id == node_run_id,
                GenerationAttempt.request_id == request_id,
                GenerationAttempt.status == "succeeded",
            )
            .with_for_update()
        )
        if attempt is None:
            raise AttemptExecutionPortError(
                "NODE_EXECUTION_ATTEMPT_NOT_SUCCEEDED",
                "the model attempt has not recorded a successful outcome",
            )
        usage = self._session.scalar(
            select(UsageRecord).where(
                UsageRecord.organization_id == self._actor.organization_id,
                UsageRecord.project_id == project_id,
                UsageRecord.node_run_id == node_run_id,
                UsageRecord.generation_attempt_id == attempt.id,
            )
        )
        if usage is None:
            raise AttemptExecutionPortError(
                "NODE_EXECUTION_USAGE_MISSING",
                "a successful attempt has no usage record",
            )
        return AttemptEvidence(
            attempt_id=attempt.id,
            usage_id=usage.id,
            attempt_no=attempt.attempt_no,
        )


def _recovery_text(details: dict[str, object]) -> str | None:
    value = details.get("recovery_text")
    return value if type(value) is str and value else None
