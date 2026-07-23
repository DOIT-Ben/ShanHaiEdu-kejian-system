from __future__ import annotations

import hashlib

import pytest

from apps.api.model_gateway.contracts import GeneratedFileFact
from apps.api.model_gateway.video_smoke import VideoProbeResult
from apps.api.video_runtime.contracts import VideoRuntimeError
from apps.api.video_runtime.validator import ObjectStorageVideoFileValidator
from tests.fakes.object_storage import FakeObjectStorage


def _stored_video() -> tuple[FakeObjectStorage, GeneratedFileFact]:
    storage = FakeObjectStorage()
    payload = b"deterministic-mp4-payload"
    digest = hashlib.sha256(payload).hexdigest()
    storage.put_bytes(
        bucket="course-assets",
        key="video-runtime/result.mp4",
        payload=payload,
        media_type="video/mp4",
    )
    return storage, GeneratedFileFact(
        storage_key="video-runtime/result.mp4",
        sha256=digest,
        size_bytes=len(payload),
        mime_type="video/mp4",
        width=1280,
        height=720,
        duration_seconds=6,
    )


def test_validator_matches_storage_hash_and_ffprobe_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage, file = _stored_video()
    monkeypatch.setattr(
        "apps.api.video_runtime.validator.probe_mp4",
        lambda *_args, **_kwargs: VideoProbeResult(
            duration_seconds=6.042,
            width=1280,
            height=720,
        ),
    )

    result = ObjectStorageVideoFileValidator(
        storage,
        storage_bucket="course-assets",
        max_bytes=1024,
    ).validate(file)

    assert result.storage_bucket == "course-assets"
    assert result.storage_key == file.storage_key
    assert result.sha256 == file.sha256
    assert result.size_bytes == file.size_bytes
    assert result.duration_ms == 6042
    assert (result.width, result.height) == (1280, 720)


@pytest.mark.parametrize(
    ("change", "probe"),
    [
        ({"sha256": "b" * 64}, VideoProbeResult(6.0, 1280, 720)),
        ({"mime_type": "video/webm"}, VideoProbeResult(6.0, 1280, 720)),
        ({"size_bytes": 1}, VideoProbeResult(6.0, 1280, 720)),
        ({}, VideoProbeResult(8.0, 1280, 720)),
        ({}, VideoProbeResult(6.0, 640, 360)),
    ],
)
def test_validator_rejects_mismatched_or_non_six_second_facts(
    monkeypatch: pytest.MonkeyPatch,
    change: dict[str, object],
    probe: VideoProbeResult,
) -> None:
    storage, file = _stored_video()
    monkeypatch.setattr(
        "apps.api.video_runtime.validator.probe_mp4",
        lambda *_args, **_kwargs: probe,
    )

    with pytest.raises(VideoRuntimeError) as caught:
        ObjectStorageVideoFileValidator(
            storage,
            storage_bucket="course-assets",
            max_bytes=1024,
        ).validate(file.model_copy(update=change))

    assert caught.value.code == "VIDEO_RUNTIME_FILE_FACT_MISMATCH"
