"""Explicit administrative CLI entry points."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.models import SYSTEM_PRINCIPAL_ID
from apps.api.ids import new_uuid7
from apps.api.logging import configure_logging
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    GeneratedFileFact,
    ModelCapability,
    ModelGatewayError,
    TextModelRequest,
    VideoGatewayResult,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
)
from apps.api.model_gateway.factory import build_real_text_gateway, build_real_video_gateway
from apps.api.model_gateway.fake import DeterministicFakeTextProvider
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.model_gateway.video_store import LocalVideoSmokeStore
from apps.api.model_gateway.video_smoke import VideoProbeError, VideoProbeResult, probe_mp4
from apps.api.model_registry import register_models
from apps.api.settings import Settings, get_settings

TEXT_SMOKE_CAPABILITIES = (ModelCapability.TEXT_SMOKE,)
VIDEO_SMOKE_CAPABILITY = ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S
VIDEO_SMOKE_DURATION_TOLERANCE_SECONDS = 1.0
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class _VideoSmokeOutcome:
    request_id: str
    result: VideoGatewayResult
    file: GeneratedFileFact
    probe: VideoProbeResult


def run_publish_golden_content(*, database_url: str | None = None, root: Path = ROOT) -> int:
    """Publish the validated built-in package and print a non-sensitive result summary."""

    if database_url is None:
        configured_database_url = get_settings().database_url
        if configured_database_url is None:
            raise RuntimeError("SHANHAI_DATABASE_URL is required for content publication")
        resolved_database_url = configured_database_url.get_secret_value()
    else:
        resolved_database_url = database_url
    source = load_builtin_courseware_release(root)
    register_models()
    engine = build_engine(resolved_database_url)
    try:
        factory = build_session_factory(engine)
        with factory() as session, session.begin():
            result = ContentReleasePublisher(session).publish(
                source,
                published_by=SYSTEM_PRINCIPAL_ID,
            )
        print(
            json.dumps(
                {
                    "conclusion": "passed",
                    "created": result.created,
                    "package_key": source.package_key,
                    "semantic_version": source.semantic_version,
                    "package_checksum": result.package_checksum,
                    "workflow_checksum": result.workflow_checksum,
                    "content_release_id": str(result.content_release_id),
                    "workflow_definition_version_id": str(result.workflow_definition_version_id),
                    "runtime_default_version_no": result.runtime_default_version_no,
                },
                ensure_ascii=True,
            )
        )
        return 0
    finally:
        engine.dispose()


async def run_model_smoke(*, capability: ModelCapability, real: bool) -> int:
    settings = get_settings()
    configure_logging(
        service="shanhaiedu-model-smoke",
        environment=settings.environment,
        level=settings.log_level,
    )
    provider = None
    if real:
        try:
            gateway, provider = build_real_text_gateway(settings)
        except ModelGatewayError as error:
            print(_error_summary(error, capability, None, None))
            return 1
    else:
        fake = DeterministicFakeTextProvider()
        gateway = ModelGateway({ModelCapability.TEXT_SMOKE: fake})

    request_id = f"req_model_smoke_{new_uuid7()}"
    try:
        result = await gateway.generate_text(
            TextModelRequest(
                capability=capability,
                request_id=request_id,
                prompt="Reply with one short confirmation token for a connectivity smoke test.",
                max_output_tokens=128,
                temperature=0,
            )
        )
    except ModelGatewayError as error:
        print(
            _error_summary(
                error,
                capability,
                settings.text_provider_name,
                settings.text_provider_model,
                request_id=request_id,
            )
        )
        return 1
    finally:
        if provider is not None:
            await provider.aclose()

    print(
        json.dumps(
            {
                "conclusion": "passed",
                "utc": datetime.now(UTC).isoformat(),
                "capability": capability.value,
                "provider": result.route.provider,
                "configured_model": result.route.model,
                "actual_model": result.actual_model,
                "request_id": result.request_id,
                "provider_request_id": result.provider_request_id,
                "latency_ms": result.latency_ms,
                "usage": result.usage.model_dump(mode="json"),
            },
            ensure_ascii=True,
        )
    )
    return 0


async def run_video_smoke(
    *,
    prompt: str,
    duration_seconds: int,
    output_dir: Path | None = None,
) -> int:
    settings = get_settings()
    configure_logging(
        service="shanhaiedu-video-smoke",
        environment=settings.environment,
        level=settings.log_level,
    )
    if not 6 <= duration_seconds <= 30:
        return _video_smoke_failure(
            settings,
            ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False),
        )
    storage = LocalVideoSmokeStore(
        output_dir or Path(tempfile.gettempdir()) / "shanhaiedu-video-smoke"
    )
    request_id = f"req_video_smoke_{new_uuid7()}"
    started_at = time.perf_counter()
    try:
        outcome = await _execute_video_smoke(
            settings=settings,
            storage=storage,
            request_id=request_id,
            prompt=prompt,
            duration_seconds=duration_seconds,
        )
    except ModelGatewayError as error:
        return _video_smoke_failure(settings, error, request_id=request_id)
    except VideoProbeError:
        return _video_smoke_failure(
            settings,
            ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False),
            request_id=request_id,
        )
    if not _matches_requested_duration(outcome.probe.duration_seconds, duration_seconds):
        return _video_smoke_failure(
            settings,
            ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False),
            request_id=request_id,
        )
    _print_video_smoke_success(
        outcome,
        elapsed_ms=int((time.perf_counter() - started_at) * 1_000),
    )
    return 0


async def _execute_video_smoke(
    *,
    settings: Settings,
    storage: LocalVideoSmokeStore,
    request_id: str,
    prompt: str,
    duration_seconds: int,
) -> _VideoSmokeOutcome:
    gateway, provider = build_real_video_gateway(settings, store=storage)
    try:
        submitted = await gateway.submit_video(
            VideoModelRequest(
                capability=VIDEO_SMOKE_CAPABILITY,
                request_id=request_id,
                prompt=prompt,
                duration_seconds=duration_seconds,
            )
        )
        result = await wait_for_video_completion(gateway, settings, submitted)
        if result.status != VideoOperationStatus.SUCCEEDED or len(result.files) != 1:
            raise ModelGatewayError(GatewayErrorCode.REJECTED, retryable=False)
        file = result.files[0]
        output_path = storage.path_for(file.storage_key)
        probe = _probe_stored_video(output_path)
        return _VideoSmokeOutcome(
            request_id=request_id,
            result=result,
            file=file,
            probe=probe,
        )
    finally:
        await provider.aclose()


async def wait_for_video_completion(
    gateway: ModelGateway,
    settings: Settings,
    result: VideoGatewayResult,
) -> VideoGatewayResult:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.video_provider_max_wait_seconds
    while result.status in {VideoOperationStatus.SUBMITTED, VideoOperationStatus.POLLING}:
        remaining_seconds = deadline - loop.time()
        if remaining_seconds <= 0:
            raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True)
        provider_task_id = result.provider_task_id
        if provider_task_id is None:
            raise ModelGatewayError(GatewayErrorCode.INVALID_RESPONSE, retryable=False)
        await asyncio.sleep(min(settings.video_provider_poll_seconds, remaining_seconds))
        if loop.time() >= deadline:
            raise ModelGatewayError(GatewayErrorCode.TIMEOUT, retryable=True)
        result = await gateway.poll_video(
            VideoPollRequest(
                capability=VIDEO_SMOKE_CAPABILITY,
                request_id=f"req_video_smoke_poll_{new_uuid7()}",
                provider_task_id=provider_task_id,
            )
        )
    return result


def _probe_stored_video(path: Path) -> VideoProbeResult:
    return probe_mp4(path)


def _video_smoke_failure(
    settings: Settings,
    error: ModelGatewayError,
    *,
    request_id: str | None = None,
) -> int:
    print(
        _error_summary(
            error,
            VIDEO_SMOKE_CAPABILITY,
            settings.video_provider_name,
            settings.video_provider_model,
            request_id=request_id,
        )
    )
    return 1


def _matches_requested_duration(actual_seconds: float, requested_seconds: int) -> bool:
    return abs(actual_seconds - requested_seconds) <= VIDEO_SMOKE_DURATION_TOLERANCE_SECONDS


def _print_video_smoke_success(outcome: _VideoSmokeOutcome, *, elapsed_ms: int) -> None:
    result = outcome.result
    file = outcome.file
    print(
        json.dumps(
            {
                "conclusion": "passed",
                "utc": datetime.now(UTC).isoformat(),
                "elapsed_ms": elapsed_ms,
                "provider": result.route.provider,
                "model": result.actual_model,
                "request_id": outcome.request_id,
                "sha256": file.sha256,
            },
            ensure_ascii=True,
        )
    )


def _error_summary(
    error: ModelGatewayError,
    capability: ModelCapability,
    provider: str | None,
    model: str | None,
    *,
    request_id: str | None = None,
) -> str:
    return json.dumps(
        {
            "conclusion": "failed",
            "utc": datetime.now(UTC).isoformat(),
            "capability": capability.value,
            "provider": provider,
            "configured_model": model,
            "request_id": request_id,
            "error_code": error.code.value,
            "retryable": error.retryable,
        },
        ensure_ascii=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ShanHaiEdu administrative commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    smoke = subparsers.add_parser("model-smoke", help="run an explicit text model smoke")
    smoke.add_argument(
        "--capability",
        choices=[capability.value for capability in TEXT_SMOKE_CAPABILITIES],
        required=True,
    )
    smoke.add_argument("--real", action="store_true")
    video_smoke = subparsers.add_parser(
        "video-smoke",
        help="run an explicit billable video Provider smoke",
    )
    video_smoke.add_argument("--prompt", required=True)
    video_smoke.add_argument("--duration-seconds", type=int, default=6)
    video_smoke.add_argument("--output-dir", type=Path)
    video_smoke.add_argument("--real", action="store_true")
    subparsers.add_parser(
        "publish-golden-content",
        help="publish the validated built-in content package and activate it for new projects",
    )
    args = parser.parse_args()
    if args.command == "model-smoke":
        return asyncio.run(
            run_model_smoke(
                capability=ModelCapability(args.capability),
                real=bool(args.real),
            )
        )
    if args.command == "video-smoke":
        if not args.real:
            parser.error("video-smoke requires --real")
        return asyncio.run(
            run_video_smoke(
                prompt=args.prompt,
                duration_seconds=args.duration_seconds,
                output_dir=args.output_dir,
            )
        )
    if args.command == "publish-golden-content":
        return run_publish_golden_content()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
