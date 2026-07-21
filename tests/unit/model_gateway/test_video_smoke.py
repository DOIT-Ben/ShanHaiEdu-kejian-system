from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from apps.api.model_gateway.video_smoke import VideoProbeError, probe_mp4


def test_probe_mp4_requires_a_video_stream_and_positive_duration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["ffprobe"],
            returncode=0,
            stdout=(
                '{"format":{"duration":"6.042"},'
                '"streams":[{"codec_type":"audio"},'
                '{"codec_type":"video","width":752,"height":416}]}'
            ),
        )

    monkeypatch.setattr("apps.api.model_gateway.video_smoke.subprocess.run", fake_run)

    result = probe_mp4(tmp_path / "result.mp4")

    assert result.duration_seconds == 6.042
    assert result.width == 752
    assert result.height == 416


def test_probe_mp4_rejects_missing_video_stream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_run(*_args, **_kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["ffprobe"],
            returncode=0,
            stdout='{"format":{"duration":"6"},"streams":[]}',
        )

    monkeypatch.setattr("apps.api.model_gateway.video_smoke.subprocess.run", fake_run)

    with pytest.raises(VideoProbeError, match="video stream"):
        probe_mp4(tmp_path / "result.mp4")
