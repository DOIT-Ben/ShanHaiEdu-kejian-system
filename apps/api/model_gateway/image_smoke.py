"""Explicit real-image smoke command with a redacted result summary."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from apps.api.ids import new_uuid7
from apps.api.logging import configure_logging
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    GeneratedFileFact,
    ImageGatewayResult,
    ImageModelRequest,
    ModelCapability,
    ModelGatewayError,
)
from apps.api.model_gateway.factory import build_real_image_gateway
from apps.api.model_gateway.image_store import LocalImageSmokeStorage
from apps.api.settings import Settings, get_settings

IMAGE_SMOKE_CAPABILITY = ModelCapability.IMAGE_GENERATE_EDUCATION_16X9
IMAGE_SMOKE_WIDTH = 1920
IMAGE_SMOKE_HEIGHT = 1080


@dataclass(frozen=True, slots=True)
class ImageSmokeOutcome:
    request_id: str
    result: ImageGatewayResult
    file: GeneratedFileFact


async def run_image_smoke(*, prompt: str, output_dir: Path | None = None) -> int:
    settings = get_settings()
    configure_logging(
        service="shanhaiedu-image-smoke",
        environment=settings.environment,
        level=settings.log_level,
    )
    storage = LocalImageSmokeStorage(
        output_dir or Path(tempfile.gettempdir()) / "shanhaiedu-image-smoke"
    )
    request_id = f"req_image_smoke_{new_uuid7()}"
    try:
        outcome = await execute_image_smoke(
            settings=settings,
            storage=storage,
            request_id=request_id,
            prompt=prompt,
        )
    except ModelGatewayError as error:
        print(_failure_summary(error, settings, request_id=request_id))
        return 1

    print(_success_summary(outcome))
    return 0


async def execute_image_smoke(
    *,
    settings: Settings,
    storage: LocalImageSmokeStorage,
    request_id: str,
    prompt: str,
) -> ImageSmokeOutcome:
    gateway, provider = build_real_image_gateway(settings, storage=storage)
    try:
        result = await gateway.generate_image(
            ImageModelRequest(
                capability=IMAGE_SMOKE_CAPABILITY,
                request_id=request_id,
                prompt=prompt,
                width=IMAGE_SMOKE_WIDTH,
                height=IMAGE_SMOKE_HEIGHT,
            )
        )
        if len(result.files) != 1:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
        return ImageSmokeOutcome(
            request_id=request_id,
            result=result,
            file=result.files[0],
        )
    finally:
        await provider.aclose()


def _success_summary(outcome: ImageSmokeOutcome) -> str:
    result = outcome.result
    file = outcome.file
    return json.dumps(
        {
            "conclusion": "passed",
            "utc": datetime.now(UTC).isoformat(),
            "provider": result.route.provider,
            "model": result.actual_model,
            "request_id": outcome.request_id,
            "provider_request_id": result.provider_request_id,
            "width": file.width,
            "height": file.height,
            "size_bytes": file.size_bytes,
            "sha256": file.sha256,
        },
        ensure_ascii=True,
    )


def _failure_summary(
    error: ModelGatewayError,
    settings: Settings,
    *,
    request_id: str,
) -> str:
    return json.dumps(
        {
            "conclusion": "failed",
            "utc": datetime.now(UTC).isoformat(),
            "capability": IMAGE_SMOKE_CAPABILITY.value,
            "provider": settings.image_provider_name,
            "configured_model": settings.image_provider_model,
            "request_id": request_id,
            "error_code": error.code.value,
            "retryable": error.retryable,
        },
        ensure_ascii=True,
    )
