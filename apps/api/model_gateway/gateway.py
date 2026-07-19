"""Capability routing and privacy-safe attempt auditing."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from apps.api.model_gateway.audit import (
    AttemptAuditSink,
    AttemptHeartbeat,
    AttemptLease,
    AttemptRequestAudit,
    AttemptSuccessAudit,
    DuplicateAttemptDelivery,
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
from apps.api.model_gateway.telemetry import (
    log_audit_recovery_failure,
    log_error,
    log_success,
)

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
        audit_heartbeat_seconds: float = 20,
    ) -> None:
        if audit_heartbeat_seconds <= 0:
            raise ValueError("audit heartbeat interval must be positive")
        self._text_routes = routes
        self._image_routes = image_routes or {}
        self._video_routes = video_routes or {}
        self._audit_sink = audit_sink
        self._audit_heartbeat_seconds = audit_heartbeat_seconds

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
            TextProviderResult,
            lambda route: route.complete(request),
            operation_kind="text_generate",
            cancellation=cancellation,
            audit_context=audit_context,
        )
        self._complete_success_audit(
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
        provider, result, attempt_id, latency_ms = await self._execute(
            request,
            self._image_routes,
            ImageProviderResult,
            lambda route: route.generate(request),
            operation_kind="image_generate",
            cancellation=cancellation,
            audit_context=audit_context,
        )
        self._complete_success_audit(
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
        provider, result, attempt_id, latency_ms = await self._execute(
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
            self._best_effort_fail_audit(
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
        self._complete_success_audit(
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

    async def _execute(
        self,
        request: GatewayRequest,
        routes: Mapping[ModelCapability, ProviderT],
        result_type: type[ProviderResultT],
        invoke: Callable[[ProviderT], Awaitable[ProviderResultT]],
        *,
        operation_kind: str,
        cancellation: CancellationToken | None,
        audit_context: ModelAuditContext | None,
    ) -> tuple[ProviderT, ProviderResultT, AttemptLease | None, int]:
        if cancellation is not None and cancellation.cancelled:
            raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
        capability = request.capability
        provider = routes.get(capability)
        try:
            attempt_lease = self._start_audit(
                request,
                audit_context,
                provider,
                operation_kind=operation_kind,
            )
        except DuplicateAttemptDelivery:
            raise ModelGatewayError(GatewayErrorCode.AUDIT_UNAVAILABLE, retryable=False) from None
        if provider is None:
            error = ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=True)
            self._best_effort_fail_audit(attempt_lease, audit_context, error, latency_ms=0)
            log_error(request, None, error.code, 0)
            raise error

        started = time.perf_counter()
        try:
            raw_result = await self._invoke_with_heartbeats(
                invoke(provider),
                attempt_lease,
                audit_context,
                cancellation,
            )
            try:
                result = result_type.model_validate(raw_result)
            except ValidationError as cause:
                raise ModelGatewayError(
                    GatewayErrorCode.INVALID_RESPONSE,
                    retryable=False,
                ) from cause
            if cancellation is not None and cancellation.cancelled:
                raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
        except asyncio.CancelledError:
            latency_ms = round((time.perf_counter() - started) * 1_000)
            error = ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
            self._best_effort_fail_audit(
                attempt_lease,
                audit_context,
                error,
                latency_ms=latency_ms,
            )
            log_error(request, provider, error.code, latency_ms)
            raise error from None
        except ModelGatewayError as error:
            latency_ms = round((time.perf_counter() - started) * 1_000)
            self._best_effort_fail_audit(
                attempt_lease,
                audit_context,
                error,
                latency_ms=latency_ms,
            )
            log_error(request, provider, error.code, latency_ms)
            raise
        except Exception as cause:
            latency_ms = round((time.perf_counter() - started) * 1_000)
            error = ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True)
            self._best_effort_fail_audit(
                attempt_lease,
                audit_context,
                error,
                latency_ms=latency_ms,
            )
            log_error(request, provider, error.code, latency_ms)
            raise error from cause
        latency_ms = round((time.perf_counter() - started) * 1_000)
        return provider, result, attempt_lease, latency_ms

    async def _invoke_with_heartbeats(
        self,
        invocation: Awaitable[ProviderResultT],
        lease: AttemptLease | None,
        context: ModelAuditContext | None,
        cancellation: CancellationToken | None,
    ) -> ProviderResultT:
        task = asyncio.ensure_future(invocation)
        if lease is None or context is None or self._audit_sink is None:
            return await task
        try:
            while True:
                done, _ = await asyncio.wait(
                    {task},
                    timeout=self._audit_heartbeat_seconds,
                )
                if done:
                    return await task
                if cancellation is not None and cancellation.cancelled:
                    await _cancel_invocation(task)
                    raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
                try:
                    heartbeat = await asyncio.to_thread(self._audit_sink.heartbeat, lease, context)
                except Exception:
                    await _cancel_invocation(task)
                    raise ModelGatewayError(
                        GatewayErrorCode.AUDIT_UNAVAILABLE,
                        retryable=False,
                    ) from None
                if heartbeat == AttemptHeartbeat.ACTIVE:
                    continue
                await _cancel_invocation(task)
                if heartbeat == AttemptHeartbeat.CANCEL_REQUESTED:
                    raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
                raise ModelGatewayError(GatewayErrorCode.AUDIT_UNAVAILABLE, retryable=False)
        except asyncio.CancelledError:
            await _cancel_invocation(task)
            raise

    def _start_audit(
        self,
        request: GatewayRequest,
        context: ModelAuditContext | None,
        provider: ProviderMetadata | None,
        *,
        operation_kind: str,
    ) -> AttemptLease | None:
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
                operation_kind=operation_kind,
            ),
            provider_name=provider.provider_name if provider else None,
            provider_model=provider.model_name if provider else None,
            route_reason="configured_primary" if provider else "no_configured_route",
        )

    def _succeed_audit(
        self,
        attempt_lease: AttemptLease | None,
        context: ModelAuditContext | None,
        result: TextProviderResult | ImageProviderResult | VideoProviderResult,
        *,
        latency_ms: int,
    ) -> None:
        if attempt_lease is None or context is None or self._audit_sink is None:
            return
        self._audit_sink.succeed(
            attempt_lease,
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

    def _complete_success_audit(
        self,
        request: GatewayRequest,
        provider: ProviderMetadata,
        result: TextProviderResult | ImageProviderResult | VideoProviderResult,
        attempt_lease: AttemptLease | None,
        context: ModelAuditContext | None,
        *,
        latency_ms: int,
        failure_code: GatewayErrorCode,
    ) -> None:
        try:
            self._succeed_audit(attempt_lease, context, result, latency_ms=latency_ms)
        except Exception:
            error = ModelGatewayError(failure_code, retryable=False)
            self._best_effort_fail_audit(
                attempt_lease,
                context,
                error,
                latency_ms=latency_ms,
            )
            log_error(request, provider, error.code, latency_ms)
            raise error from None

    def _fail_audit(
        self,
        attempt_lease: AttemptLease | None,
        context: ModelAuditContext | None,
        error: ModelGatewayError,
        *,
        latency_ms: int,
    ) -> None:
        if attempt_lease is None or context is None or self._audit_sink is None:
            return
        self._audit_sink.fail(attempt_lease, context, error, latency_ms=latency_ms)

    def _best_effort_fail_audit(
        self,
        attempt_lease: AttemptLease | None,
        context: ModelAuditContext | None,
        error: ModelGatewayError,
        *,
        latency_ms: int,
    ) -> None:
        try:
            self._fail_audit(attempt_lease, context, error, latency_ms=latency_ms)
        except Exception:
            log_audit_recovery_failure(error.code)

    @staticmethod
    def _route(capability: ModelCapability, provider: ProviderMetadata) -> RouteDecision:
        return RouteDecision(
            capability=capability,
            provider=provider.provider_name,
            model=provider.model_name,
            reason="configured_primary",
        )


async def _cancel_invocation[T](task: asyncio.Future[T]) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
