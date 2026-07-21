"""Two-transaction orchestration around one external model invocation."""

from __future__ import annotations

import asyncio
from uuid import UUID

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelGatewayError,
    ModelUsage,
    RouteDecision,
    TextGatewayResult,
)
from apps.api.model_gateway.ports import CancellationToken
from apps.api.runtime_boundary.ports import ModelInvocationPort

from .contracts import (
    CommittedNodeExecution,
    NodeExecutionError,
    NodeExecutionTransactionFactory,
    PreparedNodeExecution,
)
from .structured_output import StructuredOutputError, validate_structured_output


class NodeExecutionService:
    def __init__(
        self,
        transactions: NodeExecutionTransactionFactory,
        model: ModelInvocationPort,
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
        if prepared.pre_model_error_code is not None:
            message = prepared.pre_model_error_message or "node execution cannot invoke the model"
            self._terminalize(prepared, prepared.pre_model_error_code, cancelled=False)
            raise NodeExecutionError(prepared.pre_model_error_code, message)
        if prepared.recovered_result_text is not None:
            return self._validate_and_commit(
                prepared,
                TextGatewayResult(
                    request_id=prepared.request.request_id,
                    text=prepared.recovered_result_text,
                    route=_recovery_route(prepared),
                    provider_request_id=None,
                    actual_model="recovered-attempt",
                    finish_reason=None,
                    usage=ModelUsage(),
                    latency_ms=0,
                ),
            )
        try:
            result = await self._model.generate_text(
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
        return self._validate_and_commit(prepared, result)

    def _prepare(self, node_run_id: UUID, request_id: str) -> PreparedNodeExecution:
        with self._transactions.begin() as transaction:
            return transaction.prepare(node_run_id, request_id)

    def _validate_and_commit(
        self,
        prepared: PreparedNodeExecution,
        result: TextGatewayResult,
    ) -> CommittedNodeExecution:
        try:
            output = validate_structured_output(result.text, prepared.output_schema)
        except StructuredOutputError as exc:
            self._terminalize(prepared, exc.code, cancelled=False)
            raise NodeExecutionError(exc.code, exc.message) from exc
        try:
            with self._transactions.begin() as transaction:
                return transaction.commit(prepared, output, result)
        except NodeExecutionError as exc:
            if exc.code == "NODE_EXECUTION_CANCEL_REQUESTED":
                self._terminalize(prepared, exc.code, cancelled=True)
                raise
            code = "NODE_EXECUTION_COMMIT_FAILED"
            self._terminalize(prepared, code, cancelled=False)
            raise NodeExecutionError(code, "node execution commit failed") from exc
        except Exception as exc:
            code = "NODE_EXECUTION_COMMIT_FAILED"
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


def _recovery_route(prepared: PreparedNodeExecution) -> RouteDecision:
    return RouteDecision(
        capability=prepared.request.capability,
        provider="recovered-attempt",
        model="recovered-attempt",
        reason="persisted_attempt_result",
    )
