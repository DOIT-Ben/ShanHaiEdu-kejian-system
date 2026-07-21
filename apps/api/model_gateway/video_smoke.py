"""Local validation of a generated video smoke result."""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast


class VideoProbeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VideoProbeResult:
    duration_seconds: float
    width: int | None
    height: int | None


def probe_mp4(
    path: Path, *, executable: str = "ffprobe", timeout_seconds: float = 30
) -> VideoProbeResult:
    try:
        completed = subprocess.run(
            [
                executable,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,width,height",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VideoProbeError("ffprobe could not inspect the generated video") from exc
    if completed.returncode != 0:
        raise VideoProbeError("ffprobe rejected the generated video")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VideoProbeError("ffprobe returned invalid metadata") from exc
    if not isinstance(payload, dict):
        raise VideoProbeError("ffprobe returned invalid metadata")
    metadata = cast(dict[str, object], payload)
    duration = _duration(metadata.get("format"))
    stream = _video_stream(metadata.get("streams"))
    return VideoProbeResult(
        duration_seconds=duration,
        width=_positive_int(stream.get("width")),
        height=_positive_int(stream.get("height")),
    )


def _duration(value: object) -> float:
    if not isinstance(value, dict):
        raise VideoProbeError("ffprobe did not report a duration")
    format_metadata = cast(dict[str, object], value)
    raw_duration = format_metadata.get("duration")
    if not isinstance(raw_duration, str):
        raise VideoProbeError("ffprobe did not report a duration")
    try:
        duration = float(raw_duration)
    except ValueError as exc:
        raise VideoProbeError("ffprobe reported an invalid duration") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise VideoProbeError("ffprobe reported an invalid duration")
    return duration


def _video_stream(value: object) -> dict[str, object]:
    if not isinstance(value, list):
        raise VideoProbeError("ffprobe did not report a video stream")
    for item in cast(list[object], value):
        if isinstance(item, dict):
            stream = cast(dict[str, object], item)
            if stream.get("codec_type") == "video":
                return stream
    raise VideoProbeError("ffprobe did not report a video stream")


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and value > 0 else None
