from __future__ import annotations

import json
import subprocess
import sys
from unittest.mock import AsyncMock

import pytest

from apps.api.cli import run_model_smoke, run_video_smoke, wait_for_video_completion
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelCapability,
    ModelGatewayError,
    ModelUsage,
    RouteDecision,
    VideoGatewayResult,
    VideoOperationStatus,
)
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
