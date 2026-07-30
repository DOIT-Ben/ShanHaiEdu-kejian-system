"""Provider-specific NewAPI video submission payload construction."""

from __future__ import annotations

from uuid import UUID

from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelGatewayError,
    VideoModelRequest,
)


async def build_newapi_video_submission_payload(
    *,
    model: str,
    request: VideoModelRequest,
    organization_id: UUID | None,
    first_frame_file_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "prompt": request.prompt,
        "duration": request.duration_seconds,
    }
    if not request.references:
        if first_frame_file_id is not None:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
        return payload
    if len(request.references) != 1 or organization_id is None or first_frame_file_id is None:
        raise ModelGatewayError(GatewayErrorCode.ROUTE_UNAVAILABLE, retryable=False)
    payload["first_frame_file_id"] = first_frame_file_id
    return payload
