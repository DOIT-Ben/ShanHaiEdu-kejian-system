from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

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


def stream_response(*events: dict[str, object], done: bool = True) -> httpx.Response:
    lines = [f"data: {json.dumps(event)}\n\n" for event in events]
    if done:
        lines.append("data: [DONE]\n\n")
    return httpx.Response(
        200,
        headers={"Content-Type": "text/event-stream"},
        text="".join(lines),
    )


def success_events(
    *,
    model: str = "provider/actual-model",
    cost: float | str = 0.001,
) -> tuple[dict[str, object], ...]:
    return (
        {
            "id": "provider-request-1",
            "model": model,
            "choices": [{"delta": {"content": "SMOKE"}, "finish_reason": None}],
        },
        {
            "id": "provider-request-1",
            "model": model,
            "choices": [{"delta": {"content": "_OK"}, "finish_reason": "stop"}],
        },
        {
            "id": "provider-request-1",
            "model": model,
            "choices": [],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 2,
                "total_tokens": 7,
                "cost": cost,
            },
        },
    )


def test_config_supports_long_structured_generation_timeout() -> None:
    values = {
        "provider_name": "provider-test",
        "base_url": "https://provider.test/api/v1",
        "model": "provider/model",
        "api_key": SecretStr("test-only-key"),
    }

    assert OpenAICompatibleConfig(**values, timeout_seconds=300).timeout_seconds == 300
    with pytest.raises(ValidationError):
        OpenAICompatibleConfig(**values, timeout_seconds=301)


async def test_adapter_validates_success_and_usage() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        assert http_request.url == "https://provider.test/api/v1/chat/completions"
        assert body["model"] == "provider/model"
        assert body["stream"] is True
        assert body["stream_options"] == {"include_usage": True}
        return stream_response(*success_events())

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
        return stream_response(*success_events(model=model, cost=cost))

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
            "delta": {"content": None, "refusal": "request refused"},
            "finish_reason": "stop",
        },
        {
            "delta": {"content": None},
            "finish_reason": "error",
            "error": {"metadata": {"error_type": "refusal"}},
        },
    ],
)
async def test_adapter_maps_choice_level_refusal(choice: dict[str, object]) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return stream_response(
            {
                "id": "provider-request-refusal",
                "model": "provider/actual-model",
                "choices": [choice],
            }
        )

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.REJECTED


async def test_adapter_rejects_truncated_stream_without_done_marker() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return stream_response(*success_events(), done=False)

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE


async def test_adapter_rejects_stream_without_usage() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return stream_response(*success_events()[:2])

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "provider-request-2"),
        ("model", "provider/different-model"),
    ],
)
async def test_adapter_rejects_stream_identity_changes(field: str, value: str) -> None:
    events = list(success_events())
    events[1] = {**events[1], field: value}

    def handler(_request: httpx.Request) -> httpx.Response:
        return stream_response(*events)

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE


async def test_adapter_rejects_malformed_sse_json() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            text="data: {not-json}\n\ndata: [DONE]\n\n",
        )

    with pytest.raises(ModelGatewayError) as captured:
        await provider(handler).complete(request())

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE
