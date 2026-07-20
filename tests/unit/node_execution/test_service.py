from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

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

    def prepare(self, node_run_id: UUID, request_id: str) -> PreparedNodeExecution:
        self.events.append("prepare")
        assert node_run_id == NODE_RUN_ID
        assert request_id == "request-89"
        return prepared()

    def commit(
        self,
        execution: PreparedNodeExecution,
        output: dict[str, Any],
        result: TextGatewayResult,
    ) -> CommittedNodeExecution:
        self.events.append("commit")
        if self.commit_error is not None:
            raise self.commit_error
        assert output == {"title": "Lesson 1"}
        assert result.request_id == execution.request.request_id
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
    def __init__(self, events: list[str], *, commit_error: Exception | None = None) -> None:
        self.events = events
        self.commit_error = commit_error
        self.transactions = 0

    @contextmanager
    def begin(self) -> Iterator[FakeTransaction]:
        self.transactions += 1
        self.events.append(f"tx{self.transactions}:open")
        try:
            yield FakeTransaction(self.events, commit_error=self.commit_error)
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

    async def generate_text(
        self,
        request: TextModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> TextGatewayResult:
        self.calls += 1
        self.events.append("model")
        if self.error is not None:
            raise self.error
        return self.result


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
        "commit",
        "tx2:commit",
    ]


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
    terminal_tx = 3 if commit_error is not None else 2
    assert events[-3:] == [
        f"tx{terminal_tx}:open",
        f"terminal:{code}:False",
        f"tx{terminal_tx}:commit",
    ]
    if commit_error is not None:
        assert "tx2:rollback" in events
