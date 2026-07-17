from __future__ import annotations

from dataclasses import dataclass

import pytest

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelCapability,
    ModelGatewayError,
    TextModelRequest,
)
from apps.api.model_gateway.fake import DeterministicFakeTextProvider, FakeScenario
from apps.api.model_gateway.gateway import ModelGateway


def request() -> TextModelRequest:
    return TextModelRequest(
        capability=ModelCapability.TEXT_SMOKE,
        request_id="req-fake-smoke",
        prompt="Return a deterministic smoke marker.",
    )


@pytest.mark.parametrize(
    ("scenario", "code", "retryable"),
    [
        (FakeScenario.RATE_LIMITED, GatewayErrorCode.PROVIDER_RATE_LIMITED, True),
        (FakeScenario.TIMEOUT, GatewayErrorCode.TIMEOUT, True),
        (FakeScenario.REJECTED, GatewayErrorCode.REJECTED, False),
        (FakeScenario.UNAVAILABLE, GatewayErrorCode.PROVIDER_UNAVAILABLE, True),
        (FakeScenario.CANCELLED, GatewayErrorCode.CANCELLED, False),
    ],
)
async def test_fake_failure_scenarios_are_stable(
    scenario: FakeScenario,
    code: GatewayErrorCode,
    retryable: bool,
) -> None:
    gateway = ModelGateway({ModelCapability.TEXT_SMOKE: DeterministicFakeTextProvider(scenario)})

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.generate_text(request())

    assert captured.value.code == code
    assert captured.value.retryable is retryable


async def test_fake_success_returns_platform_contract() -> None:
    gateway = ModelGateway({ModelCapability.TEXT_SMOKE: DeterministicFakeTextProvider()})

    result = await gateway.generate_text(request())

    assert result.text == "SHANHAIEDU_FAKE_SMOKE_OK"
    assert result.route.provider == "deterministic-fake"
    assert result.usage.total_tokens == 12


async def test_missing_route_fails_without_provider_details() -> None:
    with pytest.raises(ModelGatewayError) as captured:
        await ModelGateway({}).generate_text(request())

    assert captured.value.code == GatewayErrorCode.ROUTE_UNAVAILABLE


@dataclass
class Cancelled:
    cancelled: bool = True


async def test_pre_cancelled_request_never_calls_provider() -> None:
    gateway = ModelGateway({ModelCapability.TEXT_SMOKE: DeterministicFakeTextProvider()})

    with pytest.raises(ModelGatewayError) as captured:
        await gateway.generate_text(request(), cancellation=Cancelled())

    assert captured.value.code == GatewayErrorCode.CANCELLED
