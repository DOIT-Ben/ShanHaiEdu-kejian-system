"""Capability routing and privacy-safe attempt auditing."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

from apps.api.model_gateway.audit import (
    AttemptAuditSink,
    AttemptRequestAudit,
    AttemptSuccessAudit,
    model_request_hash,
)
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ImageGatewayResult,
    ImageModelRequest,
    ImageProviderResult,
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    RouteDecision,
    TextGatewayResult,
    TextModelRequest,
    TextProviderResult,
    VideoGatewayResult,
    VideoModelRequest,
    VideoPollRequest,
    VideoProviderResult,
)
from apps.api.model_gateway.ports import (
    CancellationToken,
    ImageProvider,
    ProviderMetadata,
    TextProvider,
    VideoProvider,
)

logger = logging.getLogger(__name__)

ProviderT = TypeVar("ProviderT", bound=ProviderMetadata)
ProviderResultT = TypeVar("ProviderResultT", bound=BaseModel)
type GatewayRequest = TextModelRequest | ImageModelRequest | VideoModelRequest | VideoPollRequest


class ModelGateway:
    def __init__(
        self,
        routes: dict[ModelCapability, TextProvider],
        *,
        image_routes: dict[ModelCapability, ImageProvider] | None = None,
        video_routes: dict[ModelCapability, VideoProvider] | None = None,
        audit_sink: AttemptAuditSink | None = None,
    ) -> None:
        self._text_routes = routes
        self._image_routes = image_routes or {}
        self._video_routes = video_routes or {}
        self._audit_sink = audit_sink

    async def generate_text(
        self,
        request: TextModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> TextGatewayResult:
        provider, result, attempt_id, latency_ms = await self._execute(
            request,
            self._text_routes,
            lambda route: route.complete(request),
            cancellation=cancellation,
            audit_context=audit_context,
        )
        self._succeed_audit(attempt_id, audit_context, result, latency_ms=latency_ms)
        route = self._route(request.capability, provider)
        self._log_success(request, provider, route, result, latency_ms)
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

    async def generate_image(
        self,
        request: ImageModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> ImageGatewayResult:
        provider, result, attempt_id, latency_ms = await self._execute(
            request,
            self._image_routes,
            lambda route: route.generate(request),
            cancellation=cancellation,
            audit_context=audit_context,
        )
        self._succeed_audit(attempt_id, audit_context, result, latency_ms=latency_ms)
        route = self._route(request.capability, provider)
        self._log_success(request, provider, route, result, latency_ms)
        return ImageGatewayResult(
            request_id=request.request_id,
            route=route,
            provider_request_id=result.provider_request_id,
            actual_model=result.actual_model,
            files=result.files,
            usage=result.usage,
            latency_ms=latency_ms,
        )

    async def submit_video(
        self,
        request: VideoModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> VideoGatewayResult:
        return await self._run_video(
            request,
            lambda provider: provider.submit(request),
            cancellation=cancellation,
            audit_context=audit_context,
        )

    async def poll_video(
        self,
        request: VideoPollRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> VideoGatewayResult:
        return await self._run_video(
            request,
            lambda provider: provider.poll(request),
            cancellation=cancellation,
            audit_context=audit_context,
        )

    async def cancel_video(
        self,
        request: VideoPollRequest,
        *,
        audit_context: ModelAuditContext | None = None,
    ) -> VideoGatewayResult:
        return await self._run_video(
            request,
            lambda provider: provider.cancel(request),
            cancellation=None,
            audit_context=audit_context,
        )

    async def _run_video(
        self,
        request: VideoModelRequest | VideoPollRequest,
        invoke: Callable[[VideoProvider], Awaitable[VideoProviderResult]],
        *,
        cancellation: CancellationToken | None,
        audit_context: ModelAuditContext | None,
    ) -> VideoGatewayResult:
        provider, result, attempt_id, latency_ms = await self._execute(
            request,
            self._video_routes,
            invoke,
            cancellation=cancellation,
            audit_context=audit_context,
        )
        self._succeed_audit(attempt_id, audit_context, result, latency_ms=latency_ms)
        route = self._route(request.capability, provider)
        self._log_success(request, provider, route, result, latency_ms)
        return VideoGatewayResult(
            request_id=request.request_id,
            status=result.status,
            route=route,
            provider_request_id=result.provider_request_id,
            provider_task_id=result.provider_task_id,
            actual_model=result.actual_model,
            files=result.files,
            usage=result.usage,
            latency_ms=latency_ms,
        )

    async def _execute(
        self,
        request: GatewayRequest,
        routes: Mapping[ModelCapability, ProviderT],
        invoke: Callable[[ProviderT], Awaitable[ProviderResultT]],
        *,
        cancellation: CancellationToken | None,
        audit_context: ModelAuditContext | None,
    ) -> tuple[ProviderT, ProviderResultT, UUID | None, int]:
        if cancellation is not None and cancellation.cancelled:
            raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
        capability = request.capability
        provider = routes.get(capability)
        attempt_id = self._start_audit(request, audit_context, provider)
        if provider is None:
            error = ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=True)
            self._fail_audit(attempt_id, audit_context, error, latency_ms=0)
            self._audit_error(request, None, error.code, 0)
            raise error

        started = time.perf_counter()
        try:
            result = await invoke(provider)
            if cancellation is not None and cancellation.cancelled:
                raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
        except ModelGatewayError as error:
            latency_ms = round((time.perf_counter() - started) * 1_000)
            self._fail_audit(attempt_id, audit_context, error, latency_ms=latency_ms)
            self._audit_error(request, provider, error.code, latency_ms)
            raise
        except Exception as cause:
            latency_ms = round((time.perf_counter() - started) * 1_000)
            error = ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True)
            self._fail_audit(attempt_id, audit_context, error, latency_ms=latency_ms)
            self._audit_error(request, provider, error.code, latency_ms)
            raise error from cause
        latency_ms = round((time.perf_counter() - started) * 1_000)
        return provider, result, attempt_id, latency_ms

    def _start_audit(
        self,
        request: GatewayRequest,
        context: ModelAuditContext | None,
        provider: ProviderMetadata | None,
    ) -> UUID | None:
        if context is None or self._audit_sink is None:
            return None
        capability = request.capability
        request_id = request.request_id
        return self._audit_sink.start(
            context,
            AttemptRequestAudit(
                request_id=request_id,
                capability=capability.value,
                request_hash=model_request_hash(request),
            ),
            provider_name=provider.provider_name if provider else None,
            provider_model=provider.model_name if provider else None,
            route_reason="configured_primary" if provider else "no_configured_route",
        )

    def _succeed_audit(
        self,
        attempt_id: UUID | None,
        context: ModelAuditContext | None,
        result: TextProviderResult | ImageProviderResult | VideoProviderResult,
        *,
        latency_ms: int,
    ) -> None:
        if attempt_id is None or context is None or self._audit_sink is None:
            return
        self._audit_sink.succeed(
            attempt_id,
            context,
            AttemptSuccessAudit(
                provider_request_id=result.provider_request_id,
                provider_task_id=(
                    result.provider_task_id if isinstance(result, VideoProviderResult) else None
                ),
                actual_model=result.actual_model,
                finish_reason=(
                    result.finish_reason if isinstance(result, TextProviderResult) else None
                ),
                usage=result.usage,
            ),
            latency_ms=latency_ms,
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
    def _route(capability: ModelCapability, provider: ProviderMetadata) -> RouteDecision:
        return RouteDecision(
            capability=capability,
            provider=provider.provider_name,
            model=provider.model_name,
            reason="configured_primary",
        )

    @staticmethod
    def _log_success(
        request: GatewayRequest,
        provider: ProviderMetadata,
        route: RouteDecision,
        result: TextProviderResult | ImageProviderResult | VideoProviderResult,
        latency_ms: int,
    ) -> None:
        logger.info(
            "model_gateway_attempt_completed",
            extra={
                "request_id": request.request_id,
                "capability": route.capability.value,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "route_reason": route.reason,
                "latency_ms": latency_ms,
                "prompt_tokens": result.usage.prompt_tokens,
                "completion_tokens": result.usage.completion_tokens,
                "total_tokens": result.usage.total_tokens,
                "input_units": result.usage.input_units,
                "output_units": result.usage.output_units,
                "cost": str(result.usage.cost) if result.usage.cost is not None else None,
                "currency": result.usage.currency,
                "provider_request_id": result.provider_request_id,
                "provider_task_id": (
                    result.provider_task_id if isinstance(result, VideoProviderResult) else None
                ),
                "outcome": "succeeded",
            },
        )

    @staticmethod
    def _audit_error(
        request: GatewayRequest,
        provider: ProviderMetadata | None,
        code: GatewayErrorCode,
        latency_ms: int,
    ) -> None:
        capability = request.capability
        logger.warning(
            "model_gateway_attempt_failed",
            extra={
                "request_id": request.request_id,
                "capability": capability.value,
                "provider": provider.provider_name if provider else None,
                "model": provider.model_name if provider else None,
                "route_reason": "configured_primary" if provider else "no_configured_route",
                "latency_ms": latency_ms,
                "error_code": code.value,
                "outcome": "failed",
            },
        )
