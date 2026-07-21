from __future__ import annotations

import json
import subprocess
import sys

from apps.api.cli import run_model_smoke, run_video_smoke
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.settings import get_settings


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
