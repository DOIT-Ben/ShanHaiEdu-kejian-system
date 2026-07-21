"""Provider-specific NewAPI video submission payload construction."""

from __future__ import annotations

import asyncio
from uuid import UUID

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    MediaReference,
    ModelGatewayError,
    VideoModelRequest,
)
from apps.api.model_gateway.provider_media import (
    ProviderMediaReferenceResolver,
    ProviderMediaResolutionError,
)


async def build_newapi_video_submission_payload(
    *,
    model: str,
    request: VideoModelRequest,
    organization_id: UUID | None,
    media_reference_resolver: ProviderMediaReferenceResolver | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "prompt": request.prompt,
        "duration": request.duration_seconds,
    }
    if not request.references:
        return payload
    payload["first_frame_url"] = await _resolve_first_frame_url(
        request.references,
        organization_id=organization_id,
        resolver=media_reference_resolver,
    )
    return payload


async def _resolve_first_frame_url(
    references: list[MediaReference],
    *,
    organization_id: UUID | None,
    resolver: ProviderMediaReferenceResolver | None,
) -> str:
    if len(references) != 1 or organization_id is None or resolver is None:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    try:
        return await asyncio.to_thread(
            resolver.resolve,
            organization_id=organization_id,
            reference=references[0],
        )
    except ProviderMediaResolutionError as error:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False) from error
