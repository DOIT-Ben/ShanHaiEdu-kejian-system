"""Deterministic provider for ordinary tests and CI."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelGatewayError,
    ModelUsage,
    TextModelRequest,
    TextProviderResult,
)


class FakeScenario(StrEnum):
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"


class DeterministicFakeTextProvider:
    provider_name = "deterministic-fake"
    model_name = "fake-text-v1"

    def __init__(self, scenario: FakeScenario = FakeScenario.SUCCESS) -> None:
        self._scenario = scenario

    async def complete(self, request: TextModelRequest) -> TextProviderResult:
        errors = {
            FakeScenario.RATE_LIMITED: ModelGatewayError(
                GatewayErrorCode.PROVIDER_RATE_LIMITED,
                retryable=True,
                retry_after_seconds=1,
            ),
            FakeScenario.TIMEOUT: ModelGatewayError(
                GatewayErrorCode.TIMEOUT,
                retryable=True,
            ),
            FakeScenario.REJECTED: ModelGatewayError(
                GatewayErrorCode.REJECTED,
                retryable=False,
            ),
            FakeScenario.UNAVAILABLE: ModelGatewayError(
                GatewayErrorCode.PROVIDER_UNAVAILABLE,
                retryable=True,
            ),
            FakeScenario.CANCELLED: ModelGatewayError(
                GatewayErrorCode.CANCELLED,
                retryable=False,
            ),
        }
        if self._scenario in errors:
            raise errors[self._scenario]
        return TextProviderResult(
            text="SHANHAIEDU_FAKE_SMOKE_OK",
            provider_request_id=f"fake:{request.request_id}",
            actual_model=self.model_name,
            finish_reason="stop",
            usage=ModelUsage(
                prompt_tokens=8,
                completion_tokens=4,
                total_tokens=12,
                cost=Decimal("0"),
            ),
        )
