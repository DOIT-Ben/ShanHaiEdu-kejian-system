"""OpenAI-compatible streaming text adapter.

Wire contract sources:
- https://openrouter.ai/docs/quickstart#using-the-openrouter-api
- https://openrouter.ai/docs/api/reference/overview#responses
- https://openrouter.ai/docs/api/reference/errors-and-debugging
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import cast

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelGatewayError,
    ModelUsage,
    TextModelRequest,
    TextProviderResult,
)


class OpenAICompatibleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_name: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1, max_length=160)
    api_key: SecretStr
    timeout_seconds: float = Field(gt=0, le=300)


class _Usage(BaseModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost: Decimal | None = Field(
        default=None,
        ge=0,
        le=Decimal("999999999999.999999"),
    )


class _StreamDelta(BaseModel):
    content: str | None = None
    refusal: str | None = None


class _ErrorMetadata(BaseModel):
    error_type: str | None = None


class _ProviderError(BaseModel):
    metadata: _ErrorMetadata | None = None


class _StreamChoice(BaseModel):
    delta: _StreamDelta
    finish_reason: str | None = None
    error: _ProviderError | None = None


class _StreamCompletion(BaseModel):
    id: str | None = None
    model: str = Field(min_length=1, max_length=160)
    choices: list[_StreamChoice]
    usage: _Usage | None = None


def _invalid_response() -> ModelGatewayError:
    return ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)


def _error_type(error: object) -> str | None:
    if not isinstance(error, dict):
        return None
    error_payload = cast(dict[str, object], error)
    metadata = error_payload.get("metadata")
    if not isinstance(metadata, dict):
        return None
    metadata_payload = cast(dict[str, object], metadata)
    value = metadata_payload.get("error_type")
    return value if isinstance(value, str) else None


@dataclass(slots=True)
class _StreamState:
    request_id: str | None = None
    actual_model: str | None = None
    finish_reason: str | None = None
    usage: _Usage | None = None
    content: list[str] = field(default_factory=lambda: list[str]())
    done: bool = False

    def accept(self, payload: dict[str, object], *, status_code: int) -> None:
        if isinstance(payload.get("error"), dict):
            raise map_provider_error(status_code, _error_type(payload["error"]))
        try:
            chunk = _StreamCompletion.model_validate(payload)
        except ValidationError as exc:
            raise _invalid_response() from exc
        self._accept_identity(chunk)
        if chunk.usage is not None:
            self.usage = chunk.usage
        for choice in chunk.choices:
            if choice.error is not None:
                error_type = choice.error.metadata.error_type if choice.error.metadata else None
                raise map_provider_error(status_code, error_type)
            if choice.finish_reason == "content_filter" or choice.delta.refusal:
                raise ModelGatewayError(GatewayErrorCode.REJECTED, retryable=False)
            if choice.delta.content:
                self.content.append(choice.delta.content)
            if choice.finish_reason is not None:
                self.finish_reason = choice.finish_reason

    def result(self) -> TextProviderResult:
        text = "".join(self.content)
        if (
            not self.done
            or self.actual_model is None
            or self.finish_reason is None
            or self.usage is None
            or not text.strip()
        ):
            raise _invalid_response()
        return TextProviderResult(
            text=text,
            provider_request_id=self.request_id,
            actual_model=self.actual_model,
            finish_reason=self.finish_reason,
            usage=ModelUsage(
                prompt_tokens=self.usage.prompt_tokens,
                completion_tokens=self.usage.completion_tokens,
                total_tokens=self.usage.total_tokens,
                cost=self.usage.cost,
            ),
        )

    def _accept_identity(self, chunk: _StreamCompletion) -> None:
        if self.request_id is not None and chunk.id is not None and chunk.id != self.request_id:
            raise _invalid_response()
        if self.actual_model is not None and chunk.model != self.actual_model:
            raise _invalid_response()
        self.request_id = self.request_id or chunk.id
        self.actual_model = self.actual_model or chunk.model


def map_provider_error(status_code: int, error_type: str | None) -> ModelGatewayError:
    normalized = error_type or ""
    if status_code == 429 or normalized == "rate_limit_exceeded":
        return ModelGatewayError(GatewayErrorCode.PROVIDER_RATE_LIMITED, retryable=True)
    if status_code == 408 or normalized == "timeout":
        return ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True)
    if status_code == 401 or normalized == "authentication":
        return ModelGatewayError(GatewayErrorCode.PROVIDER_AUTH_FAILED, retryable=False)
    if status_code == 402 or normalized == "payment_required":
        return ModelGatewayError(GatewayErrorCode.PROVIDER_BUDGET_EXHAUSTED, retryable=False)
    if status_code == 404 or normalized == "not_found":
        return ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    if status_code == 403 or normalized in {
        "content_policy_violation",
        "permission_denied",
        "refusal",
    }:
        return ModelGatewayError(GatewayErrorCode.REJECTED, retryable=False)
    if 500 <= status_code < 600 or normalized in {
        "provider_overloaded",
        "provider_unavailable",
        "server",
    }:
        return ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True)
    return ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)


class OpenAICompatibleTextProvider:
    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
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

    async def complete(self, request: TextModelRequest) -> TextProviderResult:
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"
        state = _StreamState()
        try:
            async with self._client.stream(
                "POST",
                url,
                json={
                    "model": self._config.model,
                    "messages": [{"role": "user", "content": request.prompt}],
                    "max_tokens": request.max_output_tokens,
                    "temperature": request.temperature,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                },
            ) as response:
                if response.is_error:
                    await response.aread()
                    self._raise_response_error(response)
                async for event in self._sse_data(response):
                    if event == "[DONE]":
                        if state.done:
                            raise _invalid_response()
                        state.done = True
                        continue
                    if state.done:
                        raise _invalid_response()
                    try:
                        payload = json.loads(event)
                    except json.JSONDecodeError as exc:
                        raise _invalid_response() from exc
                    if not isinstance(payload, dict):
                        raise _invalid_response()
                    try:
                        state.accept(
                            cast(dict[str, object], payload), status_code=response.status_code
                        )
                    except ModelGatewayError as error:
                        self._apply_retry_after(error, response)
                        raise
        except httpx.TimeoutException as exc:
            raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True) from exc
        except httpx.RequestError as exc:
            raise ModelGatewayError(
                GatewayErrorCode.PROVIDER_UNAVAILABLE,
                retryable=True,
            ) from exc
        except asyncio.CancelledError as exc:
            raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False) from exc
        return state.result()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    async def _sse_data(response: httpx.Response) -> AsyncIterator[str]:
        data_lines: list[str] = []
        async for line in response.aiter_lines():
            if not line:
                if data_lines:
                    yield "\n".join(data_lines)
                    data_lines.clear()
                continue
            if line.startswith(":"):
                continue
            field, separator, value = line.partition(":")
            if field == "data":
                if separator and value.startswith(" "):
                    value = value[1:]
                data_lines.append(value)
                continue
            if field not in {"event", "id", "retry"}:
                raise _invalid_response()
        if data_lines:
            yield "\n".join(data_lines)

    @classmethod
    def _raise_response_error(cls, response: httpx.Response) -> None:
        try:
            data = cls._json_object(response)
        except ModelGatewayError:
            raise map_provider_error(response.status_code, None) from None
        error_type = _error_type(data.get("error"))
        mapped = map_provider_error(response.status_code, error_type)
        cls._apply_retry_after(mapped, response)
        raise mapped

    @staticmethod
    def _apply_retry_after(error: ModelGatewayError, response: httpx.Response) -> None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None and retry_after.isdigit():
            error.retry_after_seconds = int(retry_after)

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, object]:
        try:
            data = response.json()
        except ValueError as exc:
            raise ModelGatewayError(
                GatewayErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from exc
        if not isinstance(data, dict):
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
        return cast(dict[str, object], data)
