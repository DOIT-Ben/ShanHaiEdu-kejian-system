"""Transactional orchestration around one or two external model invocations."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any
from uuid import UUID

from apps.api.intro_options.generation_pipeline import (
    IntroOptionScoringError,
    build_intro_option_scoring_request,
    merge_intro_option_scores,
)
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

_MAX_EVALUATION_ATTEMPTS = 2


class NodeExecutionService:
    def __init__(
        self,
        transactions: NodeExecutionTransactionFactory,
        model: NodeExecutionModelPort,
        *,
        generation_job_id: UUID | None = None,
    ) -> None:
        self._transactions = transactions
        self._model = model
        self._generation_job_id = generation_job_id

    async def execute(
        self,
        node_run_id: UUID,
        *,
        request_id: str,
        user_revision: str | None = None,
        cancellation: CancellationToken | None = None,
    ) -> CommittedNodeExecution:
        prepared = self._prepare(node_run_id, request_id, user_revision)
        if self._generation_job_id is not None:
            prepared = replace(
                prepared,
                audit_context=replace(
                    prepared.audit_context,
                    generation_job_id=self._generation_job_id,
                ),
            )
        if prepared.committed_result is not None:
            return prepared.committed_result
        if prepared.recovery_available:
            if prepared.evaluation is not None and prepared.recovery_stage == "initial":
                if prepared.recovery_output is None:
                    self._terminalize(
                        prepared,
                        "NODE_EXECUTION_RESULT_UNAVAILABLE",
                        cancelled=False,
                    )
                    raise NodeExecutionError(
                        "NODE_EXECUTION_RESULT_UNAVAILABLE",
                        "the candidate recovery output is unavailable",
                    )
                return await self._evaluate_and_commit(
                    prepared,
                    prepared.recovery_output,
                    cancellation=cancellation,
                )
            return self._validate_and_commit(prepared, None)
        if prepared.pre_model_error_code is not None:
            message = prepared.pre_model_error_message or "node execution cannot invoke the model"
            self._terminalize(
                prepared,
                prepared.pre_model_error_code,
                cancelled=prepared.pre_model_error_code == "NODE_EXECUTION_CANCEL_REQUESTED",
            )
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
        output = self._validate_and_checkpoint(prepared, pending)
        if prepared.evaluation is not None:
            return await self._evaluate_and_commit(
                prepared,
                output,
                cancellation=cancellation,
            )
        return self._commit(prepared)

    def _prepare(
        self,
        node_run_id: UUID,
        request_id: str,
        user_revision: str | None,
    ) -> PreparedNodeExecution:
        with self._transactions.begin() as transaction:
            if user_revision is not None:
                return transaction.prepare(node_run_id, request_id, user_revision)
            return transaction.prepare(node_run_id, request_id)

    def _validate_and_commit(
        self,
        prepared: PreparedNodeExecution,
        pending: PendingTextGeneration | None,
    ) -> CommittedNodeExecution:
        if pending is None:
            return self._commit(prepared)
        self._validate_and_checkpoint(prepared, pending)
        return self._commit(prepared)

    def _validate_and_checkpoint(
        self,
        prepared: PreparedNodeExecution,
        pending: PendingTextGeneration,
    ) -> dict[str, Any]:
        try:
            output = validate_structured_output(pending.result.text, prepared.output_schema)
        except StructuredOutputError as exc:
            self._model.fail_text_pending(pending)
            self._terminalize(prepared, exc.code, cancelled=False)
            raise NodeExecutionError(exc.code, exc.message) from exc
        self._checkpoint(prepared, output, pending)
        return output

    async def _evaluate_and_commit(
        self,
        prepared: PreparedNodeExecution,
        candidates: dict[str, Any],
        *,
        cancellation: CancellationToken | None,
    ) -> CommittedNodeExecution:
        evaluation = prepared.evaluation
        if evaluation is None:
            raise NodeExecutionError(
                "NODE_EXECUTION_EVALUATION_MISSING",
                "the prepared execution has no evaluation stage",
            )
        for attempt_index in range(_MAX_EVALUATION_ATTEMPTS):
            with self._transactions.begin() as transaction:
                request_id = transaction.next_model_request_id(prepared.node_run_id)
            try:
                request = build_intro_option_scoring_request(
                    prompt_template=evaluation.prompt_template,
                    candidates=candidates,
                    output_schema=evaluation.output_schema,
                    request_id=request_id,
                )
            except IntroOptionScoringError as exc:
                self._terminalize(prepared, exc.code, cancelled=False)
                raise NodeExecutionError(exc.code, str(exc)) from exc
            try:
                pending = await self._model.generate_text_pending(
                    request,
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
            try:
                scoring = validate_structured_output(pending.result.text, evaluation.output_schema)
                merged = merge_intro_option_scores(candidates, scoring)
            except (StructuredOutputError, IntroOptionScoringError) as exc:
                self._model.fail_text_pending(pending)
                if attempt_index + 1 < _MAX_EVALUATION_ATTEMPTS:
                    continue
                self._terminalize(prepared, exc.code, cancelled=False)
                raise NodeExecutionError(exc.code, str(exc)) from exc
            final = replace(
                prepared,
                request=request,
                output_schema=evaluation.final_output_schema,
                recovery_stage=None,
                recovery_output=None,
            )
            self._checkpoint(final, merged, pending)
            return self._commit(final)
        raise AssertionError("evaluation retry loop exited without a result")

    def _checkpoint(
        self,
        prepared: PreparedNodeExecution,
        output: dict[str, Any],
        pending: PendingTextGeneration,
    ) -> None:
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
