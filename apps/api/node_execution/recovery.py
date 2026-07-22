"""Atomic storage and validation for private node-execution recovery facts."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.database import database_wall_clock
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.model_gateway.execution_port import (
    SqlAlchemyAttemptExecutionPort,
    SucceededAttempt,
)
from apps.api.model_gateway.pending import PendingTextGeneration
from apps.api.runtime_boundary.ports import WorkflowExecutionContext

from .contracts import NodeExecutionCommitContext, NodeExecutionError, PreparedNodeExecution
from .models import NodeExecutionRecoveryFact

_RECOVERY_TTL = timedelta(hours=24)
_MAX_RECOVERY_JSON_BYTES = 1_000_000


class SqlAlchemyRecoveryFactStore:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        attempts: SqlAlchemyAttemptExecutionPort,
        fault_injector: Callable[[str], None],
    ) -> None:
        self._session = session
        self._actor = actor
        self._attempts = attempts
        self._fault_injector = fault_injector

    def state(
        self,
        execution: WorkflowExecutionContext,
        succeeded: SucceededAttempt | None,
        request_id: str,
    ) -> str:
        if succeeded is None:
            return "none"
        fact = self._session.scalar(
            select(NodeExecutionRecoveryFact).where(
                NodeExecutionRecoveryFact.organization_id == self._actor.organization_id,
                NodeExecutionRecoveryFact.project_id == execution.project_id,
                NodeExecutionRecoveryFact.node_run_id == execution.node_run_id,
                NodeExecutionRecoveryFact.attempt_id == succeeded.evidence.attempt_id,
                NodeExecutionRecoveryFact.request_id == request_id,
            )
        )
        if fact is None:
            return "missing"
        if fact.expires_at <= database_wall_clock(self._session):
            self._session.delete(fact)
            self._session.flush()
            return "expired"
        return "available"

    def rebind_owner(
        self,
        execution: WorkflowExecutionContext,
        succeeded: SucceededAttempt,
        request_id: str,
        owner_token: str,
    ) -> None:
        fact = self._session.scalar(
            select(NodeExecutionRecoveryFact)
            .where(
                NodeExecutionRecoveryFact.organization_id == self._actor.organization_id,
                NodeExecutionRecoveryFact.project_id == execution.project_id,
                NodeExecutionRecoveryFact.node_run_id == execution.node_run_id,
                NodeExecutionRecoveryFact.attempt_id == succeeded.evidence.attempt_id,
                NodeExecutionRecoveryFact.request_id == request_id,
            )
            .with_for_update()
        )
        if fact is None:
            raise NodeExecutionError(
                "NODE_EXECUTION_RESULT_UNAVAILABLE",
                "the validated recovery fact is unavailable",
            )
        fact.owner_token = owner_token
        self._session.flush()

    def checkpoint(
        self,
        execution: PreparedNodeExecution,
        current: WorkflowExecutionContext,
        context: NodeExecutionCommitContext,
        owner_token: str,
        output: dict[str, Any],
        pending: PendingTextGeneration,
    ) -> None:
        if pending.result.request_id != execution.request.request_id:
            raise NodeExecutionError(
                "NODE_EXECUTION_ATTEMPT_CONTEXT_MISMATCH",
                "the pending result request does not match the frozen execution",
            )
        payload_size = _json_size(output)
        if payload_size > _MAX_RECOVERY_JSON_BYTES:
            raise NodeExecutionError(
                "NODE_EXECUTION_RECOVERY_OUTPUT_TOO_LARGE",
                "the validated output exceeds the recovery fact limit",
            )
        evidence = self._attempts.checkpoint_text_success(
            pending,
            context=execution.audit_context,
        )
        now = database_wall_clock(self._session)
        self._session.add(
            NodeExecutionRecoveryFact(
                id=new_uuid7(),
                organization_id=current.organization_id,
                project_id=current.project_id,
                workflow_run_id=current.workflow_run_id,
                node_run_id=current.node_run_id,
                attempt_id=evidence.attempt_id,
                request_id=execution.request.request_id,
                owner_token=owner_token,
                output_json=output,
                output_hash=canonical_content_hash(output),
                output_schema_digest=canonical_content_hash(execution.output_schema),
                prompt_snapshot_id=context.snapshots.prompt_snapshot_id,
                prompt_snapshot_hash=context.snapshots.prompt_hash,
                context_snapshot_id=context.snapshots.context_snapshot_id,
                context_snapshot_hash=context.snapshots.context_hash,
                max_json_bytes=_MAX_RECOVERY_JSON_BYTES,
                created_at=now,
                expires_at=now + _RECOVERY_TTL,
            )
        )
        self._session.flush()
        self._fault_injector("after_recovery_fact")

    def require(
        self,
        execution: PreparedNodeExecution,
        current: WorkflowExecutionContext,
        context: NodeExecutionCommitContext,
        owner_token: str,
    ) -> NodeExecutionRecoveryFact:
        fact = self._session.scalar(
            select(NodeExecutionRecoveryFact)
            .where(
                NodeExecutionRecoveryFact.organization_id == self._actor.organization_id,
                NodeExecutionRecoveryFact.project_id == current.project_id,
                NodeExecutionRecoveryFact.workflow_run_id == current.workflow_run_id,
                NodeExecutionRecoveryFact.node_run_id == current.node_run_id,
                NodeExecutionRecoveryFact.request_id == execution.request.request_id,
                NodeExecutionRecoveryFact.owner_token == owner_token,
            )
            .with_for_update()
        )
        if fact is None:
            raise NodeExecutionError(
                "NODE_EXECUTION_RESULT_UNAVAILABLE",
                "the validated recovery fact is unavailable",
            )
        if fact.expires_at <= database_wall_clock(self._session):
            raise NodeExecutionError(
                "NODE_EXECUTION_RECOVERY_EXPIRED",
                "the validated recovery fact expired",
            )
        if (
            fact.output_hash != canonical_content_hash(fact.output_json)
            or fact.output_schema_digest != canonical_content_hash(execution.output_schema)
            or fact.prompt_snapshot_id != context.snapshots.prompt_snapshot_id
            or fact.prompt_snapshot_hash != context.snapshots.prompt_hash
            or fact.context_snapshot_id != context.snapshots.context_snapshot_id
            or fact.context_snapshot_hash != context.snapshots.context_hash
            or fact.max_json_bytes != _MAX_RECOVERY_JSON_BYTES
            or _json_size(fact.output_json) > fact.max_json_bytes
        ):
            raise NodeExecutionError(
                "NODE_EXECUTION_RECOVERY_MISMATCH",
                "the validated recovery fact does not match the frozen execution",
            )
        return fact

    def discard(self, node_run_id: UUID) -> None:
        fact = self._session.scalar(
            select(NodeExecutionRecoveryFact)
            .where(
                NodeExecutionRecoveryFact.organization_id == self._actor.organization_id,
                NodeExecutionRecoveryFact.node_run_id == node_run_id,
            )
            .with_for_update()
        )
        if fact is not None:
            self._session.delete(fact)


def _json_size(value: Mapping[str, Any]) -> int:
    return len(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    )
