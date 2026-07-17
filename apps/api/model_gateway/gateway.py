"""Capability routing and privacy-safe attempt auditing."""

from __future__ import annotations

import logging
import time
from uuid import UUID

from apps.api.model_gateway.audit import (
    AttemptAuditSink,
    AttemptRequestAudit,
    AttemptSuccessAudit,
    model_request_hash,
)
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    RouteDecision,
    TextGatewayResult,
    TextModelRequest,
)
from apps.api.model_gateway.ports import CancellationToken, TextProvider

logger = logging.getLogger(__name__)


class ModelGateway:
    def __init__(
        self,
        routes: dict[ModelCapability, TextProvider],
        *,
        audit_sink: AttemptAuditSink | None = None,
    ) -> None:
        self._routes = routes
        self._audit_sink = audit_sink

    async def generate_text(
        self,
        request: TextModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> TextGatewayResult:
        if cancellation is not None and cancellation.cancelled:
            raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
        provider = self._routes.get(request.capability)
        route_reason = "configured_primary" if provider else "no_configured_route"
        attempt_id = self._start_audit(
            request,
            audit_context,
            provider,
            route_reason=route_reason,
        )
        if provider is None:
            error = ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=True)
            self._fail_audit(attempt_id, audit_context, error, latency_ms=0)
            self._audit_error(request, None, GatewayErrorCode.ROUTE_UNAVAILABLE, 0)
            raise error

        started = time.perf_counter()
        try:
            result = await provider.complete(request)
            if cancellation is not None and cancellation.cancelled:
                raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
        except ModelGatewayError as error:
            latency_ms = round((time.perf_counter() - started) * 1_000)
            self._fail_audit(attempt_id, audit_context, error, latency_ms=latency_ms)
            self._audit_error(request, provider, error.code, latency_ms)
            raise

        latency_ms = round((time.perf_counter() - started) * 1_000)
        route = RouteDecision(
            capability=request.capability,
            provider=provider.provider_name,
            model=provider.model_name,
            reason="configured_primary",
        )
        if attempt_id is not None and audit_context is not None and self._audit_sink is not None:
            self._audit_sink.succeed(
                attempt_id,
                audit_context,
                AttemptSuccessAudit(
                    provider_request_id=result.provider_request_id,
                    actual_model=result.actual_model,
                    finish_reason=result.finish_reason,
                    usage=result.usage,
                ),
                latency_ms=latency_ms,
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

    def _start_audit(
        self,
        request: TextModelRequest,
        context: ModelAuditContext | None,
        provider: TextProvider | None,
        *,
        route_reason: str,
    ) -> UUID | None:
        if context is None or self._audit_sink is None:
            return None
        return self._audit_sink.start(
            context,
            AttemptRequestAudit(
                request_id=request.request_id,
                capability=request.capability.value,
                request_hash=model_request_hash(request),
            ),
            provider_name=provider.provider_name if provider else None,
            provider_model=provider.model_name if provider else None,
            route_reason=route_reason,
        )

    def _fail_audit(
        self,
        attempt_id: UUID | None,
        context: ModelAuditContext | None,
        error: ModelGatewayError,
        *,
        latency_ms: int,
    ) -> None:
        if attempt_id is None or context is None or self._audit_sink is None:
            return
        self._audit_sink.fail(attempt_id, context, error, latency_ms=latency_ms)

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
