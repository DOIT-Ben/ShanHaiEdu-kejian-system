"""OpenAI-compatible non-streaming text adapter.

Wire contract sources:
- https://openrouter.ai/docs/quickstart#using-the-openrouter-api
- https://openrouter.ai/docs/api/reference/overview#responses
- https://openrouter.ai/docs/api/reference/errors-and-debugging
"""

from __future__ import annotations

import asyncio
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
    timeout_seconds: float = Field(gt=0, le=120)


class _Usage(BaseModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost: Decimal | None = Field(
        default=None,
        ge=0,
        le=Decimal("999999999999.999999"),
    )


class _Message(BaseModel):
    content: str | None
    refusal: str | None = None


class _ErrorMetadata(BaseModel):
    error_type: str | None = None


class _ProviderError(BaseModel):
    metadata: _ErrorMetadata | None = None


class _Choice(BaseModel):
    message: _Message
    finish_reason: str | None = None
    error: _ProviderError | None = None


class _Completion(BaseModel):
    id: str | None = None
    model: str = Field(min_length=1, max_length=160)
    choices: list[_Choice] = Field(min_length=1)
    usage: _Usage


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
    if status_code in {502, 503} or normalized in {
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
        try:
            response = await self._client.post(
                url,
                json={
                    "model": self._config.model,
                    "messages": [{"role": "user", "content": request.prompt}],
                    "max_tokens": request.max_output_tokens,
                    "temperature": request.temperature,
                    "stream": False,
                },
            )
        except httpx.TimeoutException as exc:
            raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True) from exc
        except httpx.RequestError as exc:
            raise ModelGatewayError(
                GatewayErrorCode.PROVIDER_UNAVAILABLE,
                retryable=True,
            ) from exc
        except asyncio.CancelledError as exc:
            raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False) from exc

        try:
            data = self._json_object(response)
        except ModelGatewayError:
            if response.is_error:
                raise map_provider_error(response.status_code, None) from None
            raise
        if response.is_error or isinstance(data.get("error"), dict):
            error_value = data.get("error")
            error = cast(dict[str, object], error_value) if isinstance(error_value, dict) else {}
            metadata_value = error.get("metadata")
            metadata = (
                cast(dict[str, object], metadata_value) if isinstance(metadata_value, dict) else {}
            )
            error_type = metadata.get("error_type")
            mapped = map_provider_error(
                response.status_code,
                error_type if isinstance(error_type, str) else None,
            )
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None and retry_after.isdigit():
                mapped.retry_after_seconds = int(retry_after)
            raise mapped

        try:
            completion = _Completion.model_validate(data)
        except ValidationError as exc:
            raise ModelGatewayError(
                GatewayErrorCode.INVALID_RESPONSE,
                retryable=False,
            ) from exc
        choice = completion.choices[0]
        if choice.error is not None:
            error_type = choice.error.metadata.error_type if choice.error.metadata else None
            raise map_provider_error(response.status_code, error_type)
        if choice.finish_reason == "content_filter" or choice.message.refusal:
            raise ModelGatewayError(GatewayErrorCode.REJECTED, retryable=False)
        content = choice.message.content
        if content is None or not content.strip():
            raise ModelGatewayError(
                GatewayErrorCode.PROVIDER_UNAVAILABLE,
                retryable=True,
            )
        return TextProviderResult(
            text=content,
            provider_request_id=completion.id,
            actual_model=completion.model,
            finish_reason=choice.finish_reason,
            usage=ModelUsage(
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                total_tokens=completion.usage.total_tokens,
                cost=completion.usage.cost,
            ),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

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
