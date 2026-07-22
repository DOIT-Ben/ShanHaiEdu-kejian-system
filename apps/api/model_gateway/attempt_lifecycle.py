"""Database wall-clock helpers for attempt lease decisions."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from apps.api.model_gateway.audit import model_request_hash
from apps.api.model_gateway.audit_contracts import (
    AttemptAuditSink,
    AttemptCompletion,
    AttemptHeartbeat,
    AttemptLease,
    AttemptRequestAudit,
    AttemptSuccessAudit,
    DuplicateAttemptDelivery,
)
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ImageModelRequest,
    ImageProviderResult,
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    TextModelRequest,
    TextProviderResult,
    VideoModelRequest,
    VideoPollRequest,
    VideoProviderResult,
)
from apps.api.model_gateway.ports import CancellationToken, ProviderMetadata
from apps.api.model_gateway.telemetry import log_audit_recovery_failure, log_error

ProviderT = TypeVar("ProviderT", bound=ProviderMetadata)
ProviderResultT = TypeVar("ProviderResultT", bound=BaseModel)
type GatewayRequest = TextModelRequest | ImageModelRequest | VideoModelRequest | VideoPollRequest


class AttemptExecutionCoordinator:
    """Run one provider invocation while its persistent attempt lease is owned."""

    def __init__(
        self,
        audit_sink: AttemptAuditSink | None,
        *,
        heartbeat_seconds: float,
    ) -> None:
        self._audit_sink = audit_sink
        self._heartbeat_seconds = heartbeat_seconds

    async def execute(
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
        provider, lease = self._prepare(request, routes, operation_kind, audit_context)
        started = time.perf_counter()
        try:
            result = await self._invoke_and_validate(
                invoke(provider), result_type, lease, audit_context, cancellation
            )
        except asyncio.CancelledError:
            error = ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
            self._record_failure(request, provider, lease, audit_context, error, started)
            raise error from None
        except ModelGatewayError as error:
            self._record_failure(request, provider, lease, audit_context, error, started)
            raise
        except Exception as cause:
            error = ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True)
            self._record_failure(request, provider, lease, audit_context, error, started)
            raise error from cause
        latency_ms = round((time.perf_counter() - started) * 1_000)
        return provider, result, lease, latency_ms

    def complete_success(
        self,
        request: GatewayRequest,
        provider: ProviderMetadata,
        result: TextProviderResult | ImageProviderResult | VideoProviderResult,
        lease: AttemptLease | None,
        context: ModelAuditContext | None,
        *,
        latency_ms: int,
        failure_code: GatewayErrorCode,
    ) -> None:
        try:
            outcome = self._succeed(lease, context, result, latency_ms=latency_ms)
        except Exception:
            error = ModelGatewayError(failure_code, retryable=False)
            self.best_effort_fail(lease, context, error, latency_ms=latency_ms)
            log_error(request, provider, error.code, latency_ms)
            raise error from None
        if outcome == AttemptCompletion.CANCELLED:
            error = ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
            log_error(request, provider, error.code, latency_ms)
            raise error from None

    def best_effort_fail(
        self,
        lease: AttemptLease | None,
        context: ModelAuditContext | None,
        error: ModelGatewayError,
        *,
        latency_ms: int,
        result: AttemptSuccessAudit | None = None,
    ) -> None:
        if lease is None or context is None or self._audit_sink is None:
            return
        try:
            if result is None:
                self._audit_sink.fail(lease, context, error, latency_ms=latency_ms)
            else:
                self._audit_sink.fail(
                    lease,
                    context,
                    error,
                    latency_ms=latency_ms,
                    result=result,
                )
        except Exception:
            log_audit_recovery_failure(error.code)

    def _prepare(
        self,
        request: GatewayRequest,
        routes: Mapping[ModelCapability, ProviderT],
        operation_kind: str,
        context: ModelAuditContext | None,
    ) -> tuple[ProviderT, AttemptLease | None]:
        provider = routes.get(request.capability)
        try:
            lease = self._start_audit(request, context, provider, operation_kind)
        except DuplicateAttemptDelivery:
            raise ModelGatewayError(GatewayErrorCode.AUDIT_UNAVAILABLE, retryable=False) from None
        if provider is None:
            error = ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=True)
            self.best_effort_fail(lease, context, error, latency_ms=0)
            log_error(request, None, error.code, 0)
            raise error
        return provider, lease

    async def _invoke_and_validate(
        self,
        invocation: Awaitable[ProviderResultT],
        result_type: type[ProviderResultT],
        lease: AttemptLease | None,
        context: ModelAuditContext | None,
        cancellation: CancellationToken | None,
    ) -> ProviderResultT:
        raw_result = await self._invoke_with_heartbeats(invocation, lease, context, cancellation)
        try:
            result = result_type.model_validate(raw_result)
        except ValidationError as cause:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False) from cause
        if cancellation is not None and cancellation.cancelled:
            raise ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False)
        return result

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
                done, _ = await asyncio.wait({task}, timeout=self._heartbeat_seconds)
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
                        GatewayErrorCode.AUDIT_UNAVAILABLE, retryable=False
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
        operation_kind: str,
    ) -> AttemptLease | None:
        if context is None or self._audit_sink is None:
            return None
        return self._audit_sink.start(
            context,
            AttemptRequestAudit(
                request_id=request.request_id,
                capability=request.capability.value,
                request_hash=model_request_hash(request),
                operation_kind=operation_kind,
            ),
            provider_name=provider.provider_name if provider else None,
            provider_model=provider.model_name if provider else None,
            route_reason="configured_primary" if provider else "no_configured_route",
        )

    def _succeed(
        self,
        lease: AttemptLease | None,
        context: ModelAuditContext | None,
        result: TextProviderResult | ImageProviderResult | VideoProviderResult,
        *,
        latency_ms: int,
    ) -> AttemptCompletion:
        if lease is None or context is None or self._audit_sink is None:
            return AttemptCompletion.SUCCEEDED
        return self._audit_sink.succeed(
            lease,
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

    def _record_failure(
        self,
        request: GatewayRequest,
        provider: ProviderMetadata,
        lease: AttemptLease | None,
        context: ModelAuditContext | None,
        error: ModelGatewayError,
        started: float,
    ) -> None:
        latency_ms = round((time.perf_counter() - started) * 1_000)
        self.best_effort_fail(lease, context, error, latency_ms=latency_ms)
        log_error(request, provider, error.code, latency_ms)


async def _cancel_invocation[T](task: asyncio.Future[T]) -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
