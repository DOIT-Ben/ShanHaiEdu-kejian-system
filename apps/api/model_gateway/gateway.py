"""Capability routing and privacy-safe attempt auditing."""

from __future__ import annotations

import logging
import time

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelCapability,
    ModelGatewayError,
    RouteDecision,
    TextGatewayResult,
    TextModelRequest,
)
from apps.api.model_gateway.ports import CancellationToken, TextProvider

logger = logging.getLogger(__name__)


class ModelGateway:
    def __init__(self, routes: dict[ModelCapability, TextProvider]) -> None:
        self._routes = routes

    async def generate_text(
        self,
        request: TextModelRequest,
        *,
        cancellation: CancellationToken | None = None,
    ) -> TextGatewayResult:
        if cancellation is not None and cancellation.cancelled:
            raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
        provider = self._routes.get(request.capability)
        if provider is None:
            self._audit_error(request, None, GatewayErrorCode.ROUTE_UNAVAILABLE, 0)
            raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=True)

        started = time.perf_counter()
        try:
            result = await provider.complete(request)
            if cancellation is not None and cancellation.cancelled:
                raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
        except ModelGatewayError as error:
            latency_ms = round((time.perf_counter() - started) * 1_000)
            self._audit_error(request, provider, error.code, latency_ms)
            raise

        latency_ms = round((time.perf_counter() - started) * 1_000)
        route = RouteDecision(
            capability=request.capability,
            provider=provider.provider_name,
            model=provider.model_name,
            reason="configured_primary",
        )
        logger.info(
            "model_gateway_attempt_completed",
            extra={
                "request_id": request.request_id,
                "capability": request.capability.value,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "route_reason": route.reason,
                "latency_ms": latency_ms,
                "prompt_tokens": result.usage.prompt_tokens,
                "completion_tokens": result.usage.completion_tokens,
                "total_tokens": result.usage.total_tokens,
                "cost": str(result.usage.cost) if result.usage.cost is not None else None,
                "currency": result.usage.currency,
                "provider_request_id": result.provider_request_id,
                "outcome": "succeeded",
            },
        )
        return TextGatewayResult(
            request_id=request.request_id,
            text=result.text,
            route=route,
            provider_request_id=result.provider_request_id,
            actual_model=result.actual_model,
            finish_reason=result.finish_reason,
            usage=result.usage,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _audit_error(
        request: TextModelRequest,
        provider: TextProvider | None,
        code: GatewayErrorCode,
        latency_ms: int,
    ) -> None:
        logger.warning(
            "model_gateway_attempt_failed",
            extra={
                "request_id": request.request_id,
                "capability": request.capability.value,
                "provider": provider.provider_name if provider else None,
                "model": provider.model_name if provider else None,
                "route_reason": "configured_primary" if provider else "no_configured_route",
                "latency_ms": latency_ms,
                "error_code": code.value,
                "outcome": "failed",
            },
        )
