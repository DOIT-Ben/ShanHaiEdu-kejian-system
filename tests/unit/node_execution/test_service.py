from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from apps.api.model_gateway.audit_contracts import AttemptLease, AttemptSuccessAudit
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    ModelUsage,
    RouteDecision,
    TextGatewayResult,
    TextModelRequest,
)
from apps.api.model_gateway.pending import PendingTextGeneration
from apps.api.model_gateway.ports import CancellationToken
from apps.api.node_execution.contracts import (
    CommittedNodeExecution,
    NodeExecutionError,
    PreparedNodeExecution,
)
from apps.api.node_execution.service import NodeExecutionService

NODE_RUN_ID = UUID("10000000-0000-4000-8000-000000000001")
ARTIFACT_VERSION_ID = UUID("10000000-0000-4000-8000-000000000002")

SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title"],
    "properties": {"title": {"type": "string", "minLength": 1}},
}


def prepared() -> PreparedNodeExecution:
    return PreparedNodeExecution(
        node_run_id=NODE_RUN_ID,
        request=TextModelRequest(
            capability=ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH,
            request_id="node-execution:10000000-0000-4000-8000-000000000001",
            prompt="Generate one JSON object.",
        ),
        audit_context=ModelAuditContext(
            organization_id=UUID("10000000-0000-4000-8000-000000000003"),
            user_id=UUID("10000000-0000-4000-8000-000000000004"),
            project_id=UUID("10000000-0000-4000-8000-000000000005"),
            node_run_id=NODE_RUN_ID,
            generation_job_id=None,
        ),
        output_schema=SCHEMA,
    )


def prepared_recovery_failure() -> PreparedNodeExecution:
    return replace(
        prepared(),
        pre_model_error_code="NODE_EXECUTION_RESULT_UNAVAILABLE",
        pre_model_error_message="the successful model result was lost before T2",
    )


def gateway_result(text: str = '{"title":"Lesson 1"}') -> TextGatewayResult:
    return TextGatewayResult(
        request_id=prepared().request.request_id,
        text=text,
        route=RouteDecision(
            capability=ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH,
            provider="deterministic-fake",
            model="fake-text-v1",
            reason="configured_primary",
        ),
        provider_request_id="fake:request",
        actual_model="fake-text-v1",
        finish_reason="stop",
        usage=ModelUsage(total_tokens=3, cost=Decimal("0")),
        latency_ms=1,
    )


@dataclass
class FakeTransaction:
    events: list[str]
    commit_error: Exception | None = None
    expected_user_revision: str | None = None

    def prepare(
        self,
        node_run_id: UUID,
        request_id: str,
        user_revision: str | None = None,
    ) -> PreparedNodeExecution:
        self.events.append("prepare")
        assert node_run_id == NODE_RUN_ID
        assert request_id == "request-89"
        assert user_revision == self.expected_user_revision
        return prepared()

    def checkpoint(
        self,
        execution: PreparedNodeExecution,
        output: dict[str, Any],
        pending: PendingTextGeneration,
    ) -> None:
        self.events.append("checkpoint")
        assert output == {"title": "Lesson 1"}
        assert pending.result.request_id == execution.request.request_id

    def commit(self, execution: PreparedNodeExecution) -> CommittedNodeExecution:
        self.events.append("commit")
        if self.commit_error is not None:
            raise self.commit_error
        return CommittedNodeExecution(
            node_run_id=execution.node_run_id,
            artifact_version_id=ARTIFACT_VERSION_ID,
            creation_package_id=None,
        )

    def terminalize_failure(
        self,
        execution: PreparedNodeExecution,
        *,
        code: str,
        cancelled: bool,
    ) -> None:
        self.events.append(f"terminal:{code}:{cancelled}")


class FakeTransactionFactory:
    def __init__(
        self,
        events: list[str],
        *,
        commit_error: Exception | None = None,
        expected_user_revision: str | None = None,
    ) -> None:
        self.events = events
        self.commit_error = commit_error
        self.expected_user_revision = expected_user_revision
        self.transactions = 0

    @contextmanager
    def begin(self) -> Iterator[FakeTransaction]:
        self.transactions += 1
        self.events.append(f"tx{self.transactions}:open")
        try:
            yield FakeTransaction(
                self.events,
                commit_error=self.commit_error,
                expected_user_revision=self.expected_user_revision,
            )
        except Exception:
            self.events.append(f"tx{self.transactions}:rollback")
            raise
        else:
            self.events.append(f"tx{self.transactions}:commit")


class RecoveryFailureTransaction(FakeTransaction):
    def prepare(self, node_run_id: UUID, request_id: str) -> PreparedNodeExecution:
        self.events.append("prepare")
        return prepared_recovery_failure()


class RecoveryFailureTransactionFactory(FakeTransactionFactory):
    @contextmanager
    def begin(self) -> Iterator[FakeTransaction]:
        self.transactions += 1
        self.events.append(f"tx{self.transactions}:open")
        transaction = RecoveryFailureTransaction(self.events)
        try:
            yield transaction
        except Exception:
            self.events.append(f"tx{self.transactions}:rollback")
            raise
        else:
            self.events.append(f"tx{self.transactions}:commit")


class FakeModel:
    def __init__(
        self,
        events: list[str],
        *,
        result: TextGatewayResult | None = None,
        error: ModelGatewayError | None = None,
    ) -> None:
        self.events = events
        self.result = result or gateway_result()
        self.error = error
        self.calls = 0

    async def generate_text_pending(
        self,
        request: TextModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> PendingTextGeneration:
        self.calls += 1
        self.events.append("model")
        if self.error is not None:
            raise self.error
        context = audit_context or prepared().audit_context
        return PendingTextGeneration(
            result=self.result,
            lease=AttemptLease(
                attempt_id=UUID("10000000-0000-4000-8000-000000000006"),
                lease_owner="unit-owner",
            ),
            audit_context=context,
            success_audit=AttemptSuccessAudit(
                provider_request_id=self.result.provider_request_id,
                provider_task_id=None,
                actual_model=self.result.actual_model,
                finish_reason=self.result.finish_reason,
                usage=self.result.usage,
            ),
        )

    def fail_text_pending(
        self,
        pending: PendingTextGeneration,
        *,
        code: GatewayErrorCode = GatewayErrorCode.INVALID_RESPONSE,
    ) -> None:
        self.events.append("model_fail")


async def test_runs_model_only_between_t1_and_t2() -> None:
    events: list[str] = []
    service = NodeExecutionService(FakeTransactionFactory(events), FakeModel(events))

    result = await service.execute(NODE_RUN_ID, request_id="request-89")

    assert result.artifact_version_id == ARTIFACT_VERSION_ID
    assert events == [
        "tx1:open",
        "prepare",
        "tx1:commit",
        "model",
        "tx2:open",
        "checkpoint",
        "tx2:commit",
        "tx3:open",
        "commit",
        "tx3:commit",
    ]


async def test_passes_teacher_revision_only_into_transactional_preparation() -> None:
    events: list[str] = []
    revision = "Use one classroom-ready counting activity."
    service = NodeExecutionService(
        FakeTransactionFactory(events, expected_user_revision=revision),
        FakeModel(events),
    )

    result = await service.execute(
        NODE_RUN_ID,
        request_id="request-89",
        user_revision=revision,
    )

    assert result.artifact_version_id == ARTIFACT_VERSION_ID


async def test_model_failure_uses_a_separate_short_terminal_transaction() -> None:
    events: list[str] = []
    model = FakeModel(
        events,
        error=ModelGatewayError(GatewayErrorCode.REJECTED, retryable=False),
    )
    service = NodeExecutionService(FakeTransactionFactory(events), model)

    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(NODE_RUN_ID, request_id="request-89")

    assert caught.value.code == GatewayErrorCode.REJECTED.value
    assert events == [
        "tx1:open",
        "prepare",
        "tx1:commit",
        "model",
        "tx2:open",
        "terminal:GENERATION_REJECTED:False",
        "tx2:commit",
    ]


async def test_lost_successful_result_fails_closed_without_reinvoking_model() -> None:
    events: list[str] = []
    model = FakeModel(events)
    service = NodeExecutionService(RecoveryFailureTransactionFactory(events), model)

    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(NODE_RUN_ID, request_id="request-89")

    assert caught.value.code == "NODE_EXECUTION_RESULT_UNAVAILABLE"
    assert model.calls == 0
    assert events == [
        "tx1:open",
        "prepare",
        "tx1:commit",
        "tx2:open",
        "terminal:NODE_EXECUTION_RESULT_UNAVAILABLE:False",
        "tx2:commit",
    ]


@pytest.mark.parametrize(
    ("model_result", "commit_error", "code"),
    [
        (gateway_result("not-json"), None, "MODEL_OUTPUT_JSON_INVALID"),
        (gateway_result(), RuntimeError("write failed"), "NODE_EXECUTION_COMMIT_FAILED"),
    ],
)
async def test_validation_or_t2_failure_never_leaves_a_partial_success(
    model_result: TextGatewayResult,
    commit_error: Exception | None,
    code: str,
) -> None:
    events: list[str] = []
    transactions = FakeTransactionFactory(events, commit_error=commit_error)
    service = NodeExecutionService(transactions, FakeModel(events, result=model_result))

    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(NODE_RUN_ID, request_id="request-89")

    assert caught.value.code == code
    terminal_tx = 4 if commit_error is not None else 2
    assert events[-3:] == [
        f"tx{terminal_tx}:open",
        f"terminal:{code}:False",
        f"tx{terminal_tx}:commit",
    ]
    if commit_error is not None:
        assert "tx3:rollback" in events
