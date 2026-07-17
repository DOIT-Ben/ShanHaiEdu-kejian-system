"""Build configured gateway routes without exposing secret values."""

from __future__ import annotations

import os

from pydantic import SecretStr

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelCapability,
    ModelGatewayError,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.model_gateway.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleTextProvider,
)
from apps.api.settings import Settings


def build_real_text_gateway(
    settings: Settings,
) -> tuple[ModelGateway, OpenAICompatibleTextProvider]:
    if not (
        settings.text_provider_name
        and settings.text_provider_base_url
        and settings.text_provider_model
    ):
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    secret = os.environ.get(settings.text_provider_secret_env)
    if not secret:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    provider = OpenAICompatibleTextProvider(
        OpenAICompatibleConfig(
            provider_name=settings.text_provider_name,
            base_url=str(settings.text_provider_base_url),
            model=settings.text_provider_model,
            api_key=SecretStr(secret),
            timeout_seconds=settings.text_provider_timeout_seconds,
        )
    )
    return ModelGateway({ModelCapability.TEXT_SMOKE: provider}), provider
