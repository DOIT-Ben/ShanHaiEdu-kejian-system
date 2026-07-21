"""Two-transaction orchestration around one external model invocation."""

from __future__ import annotations

import asyncio
from uuid import UUID

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelGatewayError,
)
from apps.api.model_gateway.pending import PendingTextGeneration
from apps.api.model_gateway.ports import CancellationToken

from .contracts import (
    CommittedNodeExecution,
    NodeExecutionError,
    NodeExecutionModelPort,
    NodeExecutionTransactionFactory,
    PreparedNodeExecution,
)
from .structured_output import StructuredOutputError, validate_structured_output


class NodeExecutionService:
    def __init__(
        self,
        transactions: NodeExecutionTransactionFactory,
        model: NodeExecutionModelPort,
    ) -> None:
        self._transactions = transactions
        self._model = model

    async def execute(
        self,
        node_run_id: UUID,
        *,
        request_id: str,
        cancellation: CancellationToken | None = None,
    ) -> CommittedNodeExecution:
        prepared = self._prepare(node_run_id, request_id)
        if prepared.committed_result is not None:
            return prepared.committed_result
        if prepared.recovery_available:
            return self._validate_and_commit(prepared, None)
        if prepared.pre_model_error_code is not None:
            message = prepared.pre_model_error_message or "node execution cannot invoke the model"
            self._terminalize(prepared, prepared.pre_model_error_code, cancelled=False)
            raise NodeExecutionError(prepared.pre_model_error_code, message)
        try:
            pending = await self._model.generate_text_pending(
                prepared.request,
                cancellation=cancellation,
                audit_context=prepared.audit_context,
            )
        except asyncio.CancelledError:
            self._terminalize(prepared, GatewayErrorCode.CANCELLED.value, cancelled=True)
            raise
        except ModelGatewayError as exc:
            cancelled = exc.code is GatewayErrorCode.CANCELLED
            self._terminalize(prepared, exc.code.value, cancelled=cancelled)
            raise NodeExecutionError(exc.code.value, "model invocation failed") from exc
        return self._validate_and_commit(prepared, pending)

    def _prepare(self, node_run_id: UUID, request_id: str) -> PreparedNodeExecution:
        with self._transactions.begin() as transaction:
            return transaction.prepare(node_run_id, request_id)

    def _validate_and_commit(
        self,
        prepared: PreparedNodeExecution,
        pending: PendingTextGeneration | None,
    ) -> CommittedNodeExecution:
        if pending is None:
            return self._commit(prepared)
        try:
            output = validate_structured_output(pending.result.text, prepared.output_schema)
        except StructuredOutputError as exc:
            self._model.fail_text_pending(pending)
            self._terminalize(prepared, exc.code, cancelled=False)
            raise NodeExecutionError(exc.code, exc.message) from exc
        try:
            with self._transactions.begin() as transaction:
                transaction.checkpoint(prepared, output, pending)
        except NodeExecutionError as exc:
            self._model.fail_text_pending(
                pending,
                code=(
                    GatewayErrorCode.CANCELLED
                    if exc.code == "NODE_EXECUTION_CANCEL_REQUESTED"
                    else GatewayErrorCode.INVALID_RESPONSE
                ),
            )
            self._terminalize(
                prepared,
                exc.code,
                cancelled=exc.code == "NODE_EXECUTION_CANCEL_REQUESTED",
            )
            raise
        except Exception as exc:
            self._model.fail_text_pending(pending)
            self._terminalize(prepared, "NODE_EXECUTION_CHECKPOINT_FAILED", cancelled=False)
            raise NodeExecutionError(
                "NODE_EXECUTION_CHECKPOINT_FAILED",
                "node execution checkpoint failed",
            ) from exc
        return self._commit(prepared)

    def _commit(self, prepared: PreparedNodeExecution) -> CommittedNodeExecution:
        try:
            with self._transactions.begin() as transaction:
                return transaction.commit(prepared)
        except NodeExecutionError as exc:
            if exc.code == "NODE_EXECUTION_CANCEL_REQUESTED":
                self._terminalize(prepared, exc.code, cancelled=True)
                raise
            self._terminalize(prepared, exc.code, cancelled=False)
            raise
        except Exception as exc:
            code = getattr(exc, "code", "NODE_EXECUTION_COMMIT_FAILED")
            self._terminalize(prepared, code, cancelled=False)
            raise NodeExecutionError(code, "node execution commit failed") from exc

    def _terminalize(
        self,
        prepared: PreparedNodeExecution,
        code: str,
        *,
        cancelled: bool,
    ) -> None:
        with self._transactions.begin() as transaction:
            transaction.terminalize_failure(prepared, code=code, cancelled=cancelled)
