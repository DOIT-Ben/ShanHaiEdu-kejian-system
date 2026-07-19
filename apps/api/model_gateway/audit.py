"""Provider-independent persistent attempt and usage audit sink."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.database import utc_now
from apps.api.ids import new_uuid7
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
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
    ) -> UUID: ...

    def succeed(
        self,
        attempt_id: UUID,
        context: ModelAuditContext,
        result: AttemptSuccessAudit,
        *,
        latency_ms: int,
    ) -> None: ...

    def fail(
        self,
        attempt_id: UUID,
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


@dataclass(frozen=True, slots=True)
class AttemptSuccessAudit:
    provider_request_id: str | None
    actual_model: str
    finish_reason: str | None
    usage: ModelUsage
    provider_task_id: str | None = None


class SqlAlchemyAttemptAuditSink:
    """Write each audit transition in its own short database transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def start(
        self,
        context: ModelAuditContext,
        request: AttemptRequestAudit,
        *,
        provider_name: str | None,
        provider_model: str | None,
        route_reason: str,
    ) -> UUID:
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
            attempt_no = session.scalar(
                select(func.coalesce(func.max(GenerationAttempt.attempt_no), 0)).where(
                    GenerationAttempt.node_run_id == context.node_run_id
                )
            )
            attempt = GenerationAttempt(
                id=new_uuid7(),
                organization_id=context.organization_id,
                project_id=context.project_id,
                node_run_id=context.node_run_id,
                generation_job_id=context.generation_job_id,
                attempt_no=int(attempt_no or 0) + 1,
                request_id=request.request_id,
                capability=request.capability,
                provider_name=provider_name,
                provider_model=provider_model,
                route_reason=route_reason,
                status="running",
                request_hash=request.request_hash,
                provider_request_id=None,
                error_details_json={},
            )
            session.add(attempt)
            session.flush()
            return attempt.id

    def succeed(
        self,
        attempt_id: UUID,
        context: ModelAuditContext,
        result: AttemptSuccessAudit,
        *,
        latency_ms: int,
    ) -> None:
        with self._session_factory() as session, session.begin():
            attempt = self._require_running(session, attempt_id, context)
            attempt.status = "succeeded"
            attempt.provider_request_id = _bounded(result.provider_request_id, 255)
            attempt.finished_at = utc_now()
            attempt.latency_ms = latency_ms
            session.add(
                self._usage_record(
                    attempt,
                    context,
                    input_units={"prompt_tokens": result.usage.prompt_tokens},
                    output_units={
                        "completion_tokens": result.usage.completion_tokens,
                        "total_tokens": result.usage.total_tokens,
                    },
                    actual_cost=result.usage.cost,
                    currency=result.usage.currency,
                    latency_ms=latency_ms,
                    provider_model=_bounded(result.actual_model, 160),
                )
            )

    def fail(
        self,
        attempt_id: UUID,
        context: ModelAuditContext,
        error: ModelGatewayError,
        *,
        latency_ms: int,
    ) -> None:
        with self._session_factory() as session, session.begin():
            attempt = self._require_running(session, attempt_id, context)
            attempt.status = "cancelled" if error.code.value == "MODEL_CANCELLED" else "failed"
            attempt.finished_at = utc_now()
            attempt.error_code = error.code.value
            attempt.error_details_json = {
                "retryable": error.retryable,
                "retry_after_seconds": error.retry_after_seconds,
            }
            attempt.latency_ms = latency_ms
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
    def _require_running(
        session: Session,
        attempt_id: UUID,
        context: ModelAuditContext,
    ) -> GenerationAttempt:
        attempt = session.scalar(
            select(GenerationAttempt)
            .where(
                GenerationAttempt.id == attempt_id,
                GenerationAttempt.organization_id == context.organization_id,
                GenerationAttempt.project_id == context.project_id,
                GenerationAttempt.node_run_id == context.node_run_id,
                GenerationAttempt.status == "running",
            )
            .with_for_update()
        )
        if attempt is None:
            raise RuntimeError("model audit attempt is missing or already terminal")
        return attempt

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
