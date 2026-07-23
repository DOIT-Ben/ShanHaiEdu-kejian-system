"""OpenAI-compatible synchronous image adapter with immutable storage facts."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
from typing import cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    GeneratedFileFact,
    ImageModelRequest,
    ImageProviderResult,
    ModelGatewayError,
    ModelUsage,
)
from apps.api.model_gateway.openai_compatible import map_provider_error
from apps.api.ppt_rendering import BackgroundImage, PptRenderingError
from apps.api.ppt_rendering.images import inspect_background
from apps.api.uploads.storage import ObjectStorage, ObjectStorageError


class OpenAICompatibleImageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1, max_length=160)
    api_key: SecretStr
    timeout_seconds: float = Field(gt=0, le=600)
    storage_bucket: str = Field(min_length=3, max_length=63)
    storage_prefix: str = Field(default="model-gateway/images", min_length=1, max_length=200)
    max_response_bytes: int = Field(gt=0, le=100_000_000)


class _ImageData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    b64_json: str = Field(min_length=1)


class _ImageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str | None = Field(default=None, max_length=160)
    data: list[_ImageData] = Field(min_length=1, max_length=1)


class OpenAICompatibleImageProvider:
    def __init__(
        self,
        config: OpenAICompatibleImageConfig,
        *,
        storage: ObjectStorage,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._storage = storage
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            headers={
                "Authorization": f"Bearer {config.api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
        )

    @property
    def provider_name(self) -> str:
        return self._config.provider_name

    @property
    def model_name(self) -> str:
        return self._config.model

    async def generate(self, request: ImageModelRequest) -> ImageProviderResult:
        try:
            response = await self._client.post(
                f"{self._config.base_url.rstrip('/')}/images/generations",
                json={
                    "model": self._config.model,
                    "prompt": request.prompt,
                    "size": f"{request.width}x{request.height}",
                    "quality": "high",
                    "response_format": "b64_json",
                    "n": 1,
                },
            )
        except httpx.TimeoutException as exc:
            raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True) from exc
        except httpx.RequestError as exc:
            raise ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True) from exc
        except asyncio.CancelledError as exc:
            raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False) from exc

        if response.is_error:
            raise _provider_error(response)
        parsed = _parse_response(response)
        content = self._decode_image(parsed.data[0].b64_json)
        self._validate_image(content, request)
        file = self._persist(content, request)

        return ImageProviderResult(
            provider_request_id=_request_id(response),
            actual_model=parsed.model or self._config.model,
            files=[file],
            usage=ModelUsage(output_units={"images": 1}),
        )

    def _persist(self, content: bytes, request: ImageModelRequest) -> GeneratedFileFact:
        key = self._storage_key(request)
        digest = hashlib.sha256(content).hexdigest()
        try:
            metadata = self._storage.put_bytes(
                bucket=self._config.storage_bucket,
                key=key,
                payload=content,
                media_type="image/png",
            )
        except ObjectStorageError as exc:
            raise ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True) from exc
        if (
            metadata.bucket != self._config.storage_bucket
            or metadata.key != key
            or metadata.media_type != "image/png"
            or metadata.size_bytes != len(content)
            or metadata.sha256 != digest
        ):
            try:
                self._storage.delete(bucket=self._config.storage_bucket, key=key)
            except ObjectStorageError:
                pass
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)

        return GeneratedFileFact(
            storage_key=key,
            sha256=digest,
            size_bytes=len(content),
            mime_type="image/png",
            width=request.width,
            height=request.height,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _decode_image(self, encoded: str) -> bytes:
        if len(encoded) > ((self._config.max_response_bytes + 2) // 3) * 4 + 4:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False) from exc
        if not content or len(content) > self._config.max_response_bytes:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
        return content

    @staticmethod
    def _validate_image(content: bytes, request: ImageModelRequest) -> None:
        try:
            info = inspect_background(BackgroundImage(content=content, media_type="image/png"))
        except PptRenderingError as exc:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False) from exc
        if info.width != request.width or info.height != request.height:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)

    def _storage_key(self, request: ImageModelRequest) -> str:
        request_hash = hashlib.sha256(request.request_id.encode("utf-8")).hexdigest()
        content_hash = hashlib.sha256(request.model_dump_json().encode("utf-8")).hexdigest()
        return f"{self._config.storage_prefix.strip('/')}/{request_hash}/{content_hash}.png"


def _parse_response(response: httpx.Response) -> _ImageResponse:
    try:
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("image response must be an object")
        return _ImageResponse.model_validate(cast(dict[str, object], payload))
    except (ValueError, ValidationError) as exc:
        raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False) from exc


def _provider_error(response: httpx.Response) -> ModelGatewayError:
    error_type: str | None = None
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = cast(dict[str, object], payload).get("error")
        if isinstance(error, dict):
            candidate = cast(dict[str, object], error).get("type")
            error_type = candidate if isinstance(candidate, str) else None
    mapped = map_provider_error(response.status_code, error_type)
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None and retry_after.isdigit():
        mapped.retry_after_seconds = int(retry_after)
    return mapped


def _request_id(response: httpx.Response) -> str | None:
    value = response.headers.get("X-Request-ID")
    if value is None or not value.strip() or len(value) > 255:
        return None
    return value
