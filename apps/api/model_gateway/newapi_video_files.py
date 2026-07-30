"""NewAPI temporary image upload contract for video references."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from apps.api.model_gateway.contracts import GatewayErrorCode, ModelGatewayError
from apps.api.model_gateway.provider_media import ProviderMediaBlob


class _GatewayFileObject(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(pattern=r"^file_[a-f0-9]{32}$")
    object: Literal["file"]
    purpose: Literal["video_reference"]
    bytes: int = Field(gt=0, le=10_485_760)
    mime_type: Literal["image/png", "image/jpeg", "image/webp"] = Field(alias="mimeType")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: AwareDatetime = Field(alias="createdAt")
    expires_at: AwareDatetime = Field(alias="expiresAt")


async def upload_temporary_video_reference(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    blob: ProviderMediaBlob,
    ttl_seconds: int,
    minimum_remaining_seconds: float,
    raise_for_error: Callable[[httpx.Response], None],
) -> str:
    try:
        response = await client.post(
            url,
            headers=headers,
            files={
                "file": (
                    _filename_for_media_type(blob.mime_type),
                    blob.content,
                    blob.mime_type,
                )
            },
            data={
                "purpose": "video_reference",
                "expires_in": str(ttl_seconds),
            },
        )
    except httpx.TimeoutException as exc:
        raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True) from exc
    except httpx.RequestError as exc:
        raise ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True) from exc
    raise_for_error(response)
    try:
        file_object = _GatewayFileObject.model_validate(response.json())
    except (ValidationError, ValueError) as exc:
        raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False) from exc
    if (
        file_object.bytes != len(blob.content)
        or file_object.mime_type != blob.mime_type
        or file_object.sha256 != blob.sha256
        or file_object.expires_at <= file_object.created_at
        or file_object.expires_at
        <= datetime.now(UTC) + timedelta(seconds=minimum_remaining_seconds)
    ):
        raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
    return file_object.id


def _filename_for_media_type(mime_type: str) -> str:
    suffixes = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }
    try:
        return f"provider-media{suffixes[mime_type]}"
    except KeyError as exc:
        raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False) from exc
