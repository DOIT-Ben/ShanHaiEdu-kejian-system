from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelCapability,
    ModelGatewayError,
    TextModelRequest,
)
from apps.api.model_gateway.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleTextProvider,
)


def request() -> TextModelRequest:
    return TextModelRequest(
        capability=ModelCapability.TEXT_SMOKE,
        request_id="req-provider-test",
        prompt="provider adapter test",
    )


def provider(handler) -> OpenAICompatibleTextProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAICompatibleTextProvider(
        OpenAICompatibleConfig(
            provider_name="provider-test",
            base_url="https://provider.test/api/v1",
            model="provider/model",
            api_key=SecretStr("test-only-key"),
            timeout_seconds=5,
        ),
        client=client,
    )


async def test_adapter_validates_success_and_usage() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        assert http_request.url == "https://provider.test/api/v1/chat/completions"
        assert body["model"] == "provider/model"
        assert body["stream"] is False
        return httpx.Response(
            200,
            json={
                "id": "provider-request-1",
                "model": "provider/actual-model",
                "choices": [{"message": {"content": "SMOKE_OK"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 2,
                    "total_tokens": 7,
                    "cost": 0.001,
                },
            },
        )

    result = await provider(handler).complete(request())

    assert result.text == "SMOKE_OK"
    assert result.provider_request_id == "provider-request-1"
    assert result.usage.total_tokens == 7


async def test_adapter_maps_error_without_exposing_raw_message() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "3"},
            json={
                "error": {
                    "message": "raw provider detail",
                    "metadata": {"error_type": "rate_limit_exceeded"},
                }
            },
        )

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.PROVIDER_RATE_LIMITED
    assert captured.value.retry_after_seconds == 3
    assert "raw provider detail" not in str(captured.value)


async def test_adapter_rejects_invalid_success_shape() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE


@pytest.mark.parametrize(
    ("model", "cost"),
    [
        ("m" * 161, 0.001),
        ("provider/actual-model", "1000000000000.000000"),
    ],
)
async def test_adapter_rejects_audit_metadata_outside_database_bounds(
    model: str,
    cost: float | str,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "provider-request-out-of-bounds",
                "model": model,
                "choices": [{"message": {"content": "SMOKE_OK"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 2,
                    "total_tokens": 7,
                    "cost": cost,
                },
            },
        )

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE


async def test_non_json_provider_outage_remains_retryable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream unavailable")

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.PROVIDER_UNAVAILABLE
    assert captured.value.retryable is True


async def test_http_timeout_maps_to_platform_timeout() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider timeout", request=http_request)

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.TIMEOUT
    assert captured.value.retryable is True


@pytest.mark.parametrize(
    "choice",
    [
        {
            "message": {"content": None, "refusal": "request refused"},
            "finish_reason": "stop",
        },
        {
            "message": {"content": None},
            "finish_reason": "error",
            "error": {"metadata": {"error_type": "refusal"}},
        },
    ],
)
async def test_adapter_maps_choice_level_refusal(choice: dict[str, object]) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "provider-request-refusal",
                "model": "provider/actual-model",
                "choices": [choice],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 0,
                    "total_tokens": 5,
                },
            },
        )

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.REJECTED
