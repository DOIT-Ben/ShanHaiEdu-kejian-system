from __future__ import annotations

import base64
import json

import httpx
import pytest
from pydantic import SecretStr

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ImageModelRequest,
    ModelCapability,
    ModelGatewayError,
)
from apps.api.model_gateway.openai_compatible_image import (
    OpenAICompatibleImageConfig,
    OpenAICompatibleImageProvider,
)
from tests.fakes.object_storage import FakeObjectStorage
from tests.unit.ppt_rendering.helpers import png_bytes


def request(*, width: int = 160, height: int = 90) -> ImageModelRequest:
    return ImageModelRequest(
        capability=ModelCapability.IMAGE_GENERATE_EDUCATION_16X9,
        request_id="req-image-provider-test",
        prompt="Paper-clay primary math background without text or numerals.",
        width=width,
        height=height,
    )


def provider(handler) -> tuple[OpenAICompatibleImageProvider, FakeObjectStorage]:
    storage = FakeObjectStorage()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return (
        OpenAICompatibleImageProvider(
            OpenAICompatibleImageConfig(
                provider_name="newapi-image-test",
                base_url="https://provider.test/v1",
                model="gpt-image-2",
                api_key=SecretStr("test-only-key"),
                timeout_seconds=5,
                storage_bucket="shanhaiedu",
                storage_prefix="golden/images",
                max_response_bytes=1_000_000,
            ),
            storage=storage,
            client=client,
        ),
        storage,
    )


async def test_adapter_persists_exact_png_and_returns_file_fact(tmp_path) -> None:
    payload = png_bytes(width=160, height=90)

    def handler(http_request: httpx.Request) -> httpx.Response:
        body = json.loads(http_request.content)
        assert http_request.url == "https://provider.test/v1/images/generations"
        assert body == {
            "model": "gpt-image-2",
            "prompt": "Paper-clay primary math background without text or numerals.",
            "size": "160x90",
            "quality": "high",
            "response_format": "b64_json",
            "n": 1,
        }
        return httpx.Response(
            200,
            headers={"X-Request-ID": "provider-image-request-1"},
            json={
                "model": "gpt-image-2",
                "data": [{"b64_json": base64.b64encode(payload).decode("ascii")}],
            },
        )

    adapter, storage = provider(handler)
    result = await adapter.generate(request())

    assert result.provider_request_id == "provider-image-request-1"
    assert result.actual_model == "gpt-image-2"
    assert result.usage.output_units == {"images": 1}
    assert len(result.files) == 1
    file = result.files[0]
    assert file.mime_type == "image/png"
    assert file.width == 160
    assert file.height == 90
    assert file.storage_key.startswith("golden/images/")
    destination = tmp_path / "generated.png"
    storage.download_to_path(
        bucket="shanhaiedu",
        key=file.storage_key,
        destination=destination,
        max_bytes=1_000_000,
    )
    assert destination.read_bytes() == payload


@pytest.mark.parametrize(
    "encoded",
    [
        "not-base64!",
        base64.b64encode(b"not-an-image").decode("ascii"),
        base64.b64encode(png_bytes(width=90, height=90)).decode("ascii"),
    ],
)
async def test_adapter_rejects_invalid_or_wrong_dimension_image(encoded: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})

    adapter, storage = provider(handler)
    with pytest.raises(ModelGatewayError) as captured:
        await adapter.generate(request())

    assert captured.value.code == GatewayErrorCode.INVALID_RESPONSE
    assert storage.object_count == 0


async def test_adapter_maps_provider_error_without_exposing_raw_message() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "4"},
            json={"error": {"type": "rate_limit_exceeded", "message": "private detail"}},
        )

    adapter, _storage = provider(handler)
    with pytest.raises(ModelGatewayError) as captured:
        await adapter.generate(request())

    assert captured.value.code == GatewayErrorCode.PROVIDER_RATE_LIMITED
    assert captured.value.retry_after_seconds == 4
    assert "private detail" not in str(captured.value)
