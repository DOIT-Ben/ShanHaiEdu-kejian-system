from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.cli import (
    _VideoSmokeOutcome,
    run_model_smoke,
    run_video_smoke,
    wait_for_video_completion,
)
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    GeneratedFileFact,
    ModelCapability,
    ModelGatewayError,
    ModelUsage,
    RouteDecision,
    VideoGatewayResult,
    VideoOperationStatus,
)
from apps.api.model_gateway.video_smoke import VideoProbeResult
from apps.api.settings import Settings, get_settings


async def test_fake_cli_summary_excludes_prompt_and_model_text(capsys) -> None:
    get_settings.cache_clear()
    try:
        exit_code = await run_model_smoke(
            capability=ModelCapability.TEXT_SMOKE,
            real=False,
        )
    finally:
        get_settings.cache_clear()

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["conclusion"] == "passed"
    assert "text" not in summary
    assert "prompt" not in summary
    assert "SHANHAIEDU_FAKE_SMOKE_OK" not in json.dumps(summary)


async def test_video_smoke_configuration_failure_excludes_prompt(capsys) -> None:
    get_settings.cache_clear()
    try:
        exit_code = await run_video_smoke(
            prompt="must-not-appear-in-a-video-smoke-summary",
            duration_seconds=6,
        )
    finally:
        get_settings.cache_clear()

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert summary["conclusion"] == "failed"
    assert "prompt" not in summary
    assert "must-not-appear" not in json.dumps(summary)


async def test_video_smoke_rejects_an_unpaired_private_media_selector(capsys) -> None:
    exit_code = await run_video_smoke(
        prompt="a short test video",
        duration_seconds=6,
        file_version_id=uuid4(),
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert summary["error_code"] == GatewayErrorCode.INVALID_RESPONSE.value


async def test_video_smoke_success_uses_the_minimal_auditable_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    tmp_path: Path,
) -> None:
    request_id = "req_video_smoke_018f0000-0000-7000-8000-000000000001"
    outcome = _video_smoke_outcome(
        request_id=request_id,
        duration_seconds=6.042,
    )

    async def execute(**_kwargs) -> _VideoSmokeOutcome:
        return outcome

    times = iter((10.0, 12.345))
    monkeypatch.setattr("apps.api.cli._execute_video_smoke", execute)
    monkeypatch.setattr("apps.api.cli.time.perf_counter", lambda: next(times))

    exit_code = await run_video_smoke(
        prompt="must-not-appear-in-a-video-smoke-summary",
        duration_seconds=6,
        output_dir=tmp_path,
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert set(summary) == {
        "conclusion",
        "utc",
        "elapsed_ms",
        "provider",
        "model",
        "request_id",
        "sha256",
    }
    assert summary["conclusion"] == "passed"
    assert summary["elapsed_ms"] == 2_345
    assert summary["request_id"] == request_id
    assert "must-not-appear" not in json.dumps(summary)
    assert "provider-task" not in json.dumps(summary)
    assert str(tmp_path) not in json.dumps(summary)


async def test_video_smoke_rejects_a_result_outside_the_requested_duration(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    tmp_path: Path,
) -> None:
    outcome = _video_smoke_outcome(
        request_id="req_video_smoke_018f0000-0000-7000-8000-000000000002",
        duration_seconds=6.042,
    )

    async def execute(**_kwargs) -> _VideoSmokeOutcome:
        return outcome

    monkeypatch.setattr("apps.api.cli._execute_video_smoke", execute)

    exit_code = await run_video_smoke(
        prompt="a short test video",
        duration_seconds=30,
        output_dir=tmp_path,
    )

    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert summary["conclusion"] == "failed"
    assert summary["error_code"] == GatewayErrorCode.INVALID_RESPONSE.value


def _video_smoke_outcome(
    *,
    request_id: str,
    duration_seconds: float,
) -> _VideoSmokeOutcome:
    return _VideoSmokeOutcome(
        request_id=request_id,
        result=VideoGatewayResult(
            request_id="req_video_smoke_poll_018f0000-0000-7000-8000-000000000003",
            status=VideoOperationStatus.SUCCEEDED,
            route=RouteDecision(
                capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
                provider="newapi",
                model="configured-video-grok",
                reason="configured_primary",
            ),
            provider_request_id="provider-request-1",
            provider_task_id="provider-task-1",
            actual_model="video-grok",
            files=[
                GeneratedFileFact(
                    storage_key="model-smoke/video/result.mp4",
                    sha256="a" * 64,
                    size_bytes=42,
                    mime_type="video/mp4",
                )
            ],
            usage=ModelUsage(),
            latency_ms=1,
        ),
        file=GeneratedFileFact(
            storage_key="model-smoke/video/result.mp4",
            sha256="a" * 64,
            size_bytes=42,
            mime_type="video/mp4",
        ),
        probe=VideoProbeResult(
            duration_seconds=duration_seconds,
            width=752,
            height=416,
        ),
    )


def test_text_smoke_cli_rejects_non_text_capability_without_traceback() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "apps.api.cli",
            "model-smoke",
            "--capability",
            ModelCapability.IMAGE_GENERATE_EDUCATION_16X9.value,
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "invalid choice" in result.stderr
    assert "Traceback" not in result.stderr


def test_video_smoke_cli_requires_an_explicit_real_flag() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "apps.api.cli",
            "video-smoke",
            "--prompt",
            "a short test video",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "requires --real" in result.stderr
    assert "Traceback" not in result.stderr


async def test_video_smoke_poll_wait_never_exceeds_its_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Clock:
        def __init__(self) -> None:
            self._values = iter((0.0, 0.0, 10.0))

        def time(self) -> float:
            return next(self._values)

    sleep_delays: list[float] = []

    async def sleep(delay: float) -> None:
        sleep_delays.append(delay)

    monkeypatch.setattr("apps.api.cli.asyncio.get_running_loop", lambda: Clock())
    monkeypatch.setattr("apps.api.cli.asyncio.sleep", sleep)
    gateway = AsyncMock()
    submitted = VideoGatewayResult(
        request_id="req-video-submitted",
        status=VideoOperationStatus.SUBMITTED,
        route=RouteDecision(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            provider="newapi",
            model="video-grok",
            reason="configured_primary",
        ),
        provider_request_id="provider-request-1",
        provider_task_id="provider-task-1",
        actual_model="video-grok",
        files=[],
        usage=ModelUsage(),
        latency_ms=1,
    )
    settings = Settings(
        _env_file=None,
        video_provider_max_wait_seconds=10,
        video_provider_poll_seconds=60,
    )

    with pytest.raises(ModelGatewayError) as captured:
        await wait_for_video_completion(gateway, settings, submitted)

    assert captured.value.code == GatewayErrorCode.TIMEOUT
    assert sleep_delays == [10]
    gateway.poll_video.assert_not_awaited()
