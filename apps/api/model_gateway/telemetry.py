"""Privacy-safe model gateway logging."""

from __future__ import annotations

import hashlib
import logging
from typing import Protocol

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ImageProviderResult,
    ModelCapability,
    RouteDecision,
    TextProviderResult,
    VideoProviderResult,
)
from apps.api.model_gateway.ports import ProviderMetadata

logger = logging.getLogger(__name__)

type ProviderResult = TextProviderResult | ImageProviderResult | VideoProviderResult


class GatewayLogRequest(Protocol):
    @property
    def request_id(self) -> str: ...

    @property
    def capability(self) -> ModelCapability: ...


def log_success(
    request: GatewayLogRequest,
    provider: ProviderMetadata,
    route: RouteDecision,
    result: ProviderResult,
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
            "provider_request_hash": _identifier_hash(result.provider_request_id),
            "provider_task_hash": _identifier_hash(
                result.provider_task_id if isinstance(result, VideoProviderResult) else None
            ),
            "outcome": "succeeded",
        },
    )


def log_error(
    request: GatewayLogRequest,
    provider: ProviderMetadata | None,
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


def log_audit_recovery_failure(code: GatewayErrorCode) -> None:
    logger.error(
        "model_gateway_audit_recovery_failed",
        extra={"error_code": code.value},
    )


def _identifier_hash(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
