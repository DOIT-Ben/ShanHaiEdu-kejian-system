"""Capability routing and privacy-safe attempt auditing."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from apps.api.model_gateway.attempt_lifecycle import AttemptExecutionCoordinator
from apps.api.model_gateway.audit_contracts import AttemptAuditSink
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
    VideoOperationStatus,
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
from apps.api.model_gateway.telemetry import log_error, log_success


class ModelGateway:
    def __init__(
        self,
        routes: dict[ModelCapability, TextProvider],
        *,
        image_routes: dict[ModelCapability, ImageProvider] | None = None,
        video_routes: dict[ModelCapability, VideoProvider] | None = None,
        audit_sink: AttemptAuditSink | None = None,
        audit_heartbeat_seconds: float = 20,
    ) -> None:
        if audit_heartbeat_seconds <= 0:
            raise ValueError("audit heartbeat interval must be positive")
        self._text_routes = routes
        self._image_routes = image_routes or {}
        self._video_routes = video_routes or {}
        self._attempts = AttemptExecutionCoordinator(
            audit_sink,
            heartbeat_seconds=audit_heartbeat_seconds,
        )

    async def generate_text(
        self,
        request: TextModelRequest,
        *,
        cancellation: CancellationToken | None = None,
        audit_context: ModelAuditContext | None = None,
    ) -> TextGatewayResult:
        provider, result, attempt_id, latency_ms = await self._attempts.execute(
            request,
            self._text_routes,
            TextProviderResult,
            lambda route: route.complete(request),
            operation_kind="text_generate",
            cancellation=cancellation,
            audit_context=audit_context,
        )
        self._attempts.complete_success(
            request,
            provider,
            result,
            attempt_id,
            audit_context,
            latency_ms=latency_ms,
            failure_code=GatewayErrorCode.AUDIT_UNAVAILABLE,
        )
        route = self._route(request.capability, provider)
        log_success(request, provider, route, result, latency_ms)
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
        provider, result, attempt_id, latency_ms = await self._attempts.execute(
            request,
            self._image_routes,
            ImageProviderResult,
            lambda route: route.generate(request),
            operation_kind="image_generate",
            cancellation=cancellation,
            audit_context=audit_context,
        )
        self._attempts.complete_success(
            request,
            provider,
            result,
            attempt_id,
            audit_context,
            latency_ms=latency_ms,
            failure_code=GatewayErrorCode.AUDIT_UNAVAILABLE,
        )
        route = self._route(request.capability, provider)
        log_success(request, provider, route, result, latency_ms)
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
            operation_kind="video_submit",
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
            operation_kind="video_poll",
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
            operation_kind="video_cancel",
            cancellation=None,
            audit_context=audit_context,
        )

    async def _run_video(
        self,
        request: VideoModelRequest | VideoPollRequest,
        invoke: Callable[[VideoProvider], Awaitable[VideoProviderResult]],
        *,
        operation_kind: str,
        cancellation: CancellationToken | None,
        audit_context: ModelAuditContext | None,
    ) -> VideoGatewayResult:
        provider, result, attempt_id, latency_ms = await self._attempts.execute(
            request,
            self._video_routes,
            VideoProviderResult,
            invoke,
            operation_kind=operation_kind,
            cancellation=cancellation,
            audit_context=audit_context,
        )
        if result.status == VideoOperationStatus.SUBMISSION_UNKNOWN:
            error = ModelGatewayError(GatewayErrorCode.SUBMISSION_UNKNOWN, retryable=False)
            self._attempts.best_effort_fail(
                attempt_id,
                audit_context,
                error,
                latency_ms=latency_ms,
            )
            log_error(request, provider, error.code, latency_ms)
            raise error from None
        failure_code = (
            GatewayErrorCode.SUBMISSION_UNKNOWN
            if isinstance(request, VideoModelRequest)
            else GatewayErrorCode.AUDIT_UNAVAILABLE
        )
        self._attempts.complete_success(
            request,
            provider,
            result,
            attempt_id,
            audit_context,
            latency_ms=latency_ms,
            failure_code=failure_code,
        )
        route = self._route(request.capability, provider)
        log_success(request, provider, route, result, latency_ms)
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

    @staticmethod
    def _route(capability: ModelCapability, provider: ProviderMetadata) -> RouteDecision:
        return RouteDecision(
            capability=capability,
            provider=provider.provider_name,
            model=provider.model_name,
            reason="configured_primary",
        )
