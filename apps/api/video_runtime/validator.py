"""Object-storage and ffprobe validation for generated classroom-intro videos."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NoReturn

from apps.api.model_gateway.contracts import GeneratedFileFact, VideoGatewayResult
from apps.api.model_gateway.video_smoke import VideoProbeError, probe_mp4
from apps.api.uploads.storage import ObjectMetadata, ObjectStorage, ObjectStorageError

from .contracts import ValidatedVideoFile, VideoRuntimeError


def require_validated_gateway_file(
    gateway_result: VideoGatewayResult,
    validated: ValidatedVideoFile,
) -> None:
    file = gateway_result.files[0]
    if (
        file.storage_key != validated.storage_key
        or file.mime_type != validated.mime_type
        or file.size_bytes != validated.size_bytes
        or file.sha256 != validated.sha256
    ):
        raise VideoRuntimeError(
            "VIDEO_RUNTIME_FILE_FACT_MISMATCH",
            "validated video facts differ from the provider result",
        )


class ObjectStorageVideoFileValidator:
    def __init__(
        self,
        storage: ObjectStorage,
        *,
        storage_bucket: str,
        max_bytes: int,
        expected_duration_seconds: float = 6.0,
        duration_tolerance_seconds: float = 0.75,
        ffprobe_executable: str = "ffprobe",
        ffprobe_timeout_seconds: float = 30,
    ) -> None:
        if not storage_bucket.strip() or max_bytes < 1:
            raise ValueError("video storage bucket and positive download limit are required")
        if expected_duration_seconds <= 0 or duration_tolerance_seconds < 0:
            raise ValueError("video duration validation settings are invalid")
        self._storage = storage
        self._storage_bucket = storage_bucket
        self._max_bytes = max_bytes
        self._expected_duration_seconds = expected_duration_seconds
        self._duration_tolerance_seconds = duration_tolerance_seconds
        self._ffprobe_executable = ffprobe_executable
        self._ffprobe_timeout_seconds = ffprobe_timeout_seconds

    def validate(self, file: GeneratedFileFact) -> ValidatedVideoFile:
        try:
            stat = self._storage.stat(
                bucket=self._storage_bucket,
                key=file.storage_key,
            )
            self._require_storage_match(file, stat)
            with TemporaryDirectory(prefix="shanhai-video-validate-") as directory:
                path = Path(directory) / "candidate.mp4"
                downloaded = self._storage.download_to_path(
                    bucket=self._storage_bucket,
                    key=file.storage_key,
                    destination=path,
                    max_bytes=self._max_bytes,
                )
                self._require_storage_match(file, downloaded)
                if downloaded != stat:
                    self._mismatch()
                probe = probe_mp4(
                    path,
                    executable=self._ffprobe_executable,
                    timeout_seconds=self._ffprobe_timeout_seconds,
                )
        except VideoRuntimeError:
            raise
        except (ObjectStorageError, VideoProbeError, OSError, ValueError) as exc:
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_FILE_FACT_MISMATCH",
                "generated video file facts do not match storage or ffprobe",
            ) from exc

        width = probe.width
        height = probe.height
        if (
            width is None
            or height is None
            or (file.width is not None and width != file.width)
            or (file.height is not None and height != file.height)
            or abs(probe.duration_seconds - self._expected_duration_seconds)
            > self._duration_tolerance_seconds
            or (
                file.duration_seconds is not None
                and abs(probe.duration_seconds - file.duration_seconds)
                > self._duration_tolerance_seconds
            )
        ):
            self._mismatch()
        return ValidatedVideoFile(
            storage_bucket=stat.bucket,
            storage_key=stat.key,
            etag=stat.etag,
            mime_type=stat.media_type,
            size_bytes=stat.size_bytes,
            sha256=file.sha256,
            width=width,
            height=height,
            duration_ms=round(probe.duration_seconds * 1000),
        )

    @staticmethod
    def _require_storage_match(file: GeneratedFileFact, metadata: ObjectMetadata) -> None:
        if (
            file.mime_type != "video/mp4"
            or metadata.media_type != file.mime_type
            or metadata.size_bytes != file.size_bytes
            or metadata.sha256 != file.sha256
            or not metadata.etag
        ):
            ObjectStorageVideoFileValidator._mismatch()

    @staticmethod
    def _mismatch() -> NoReturn:
        raise VideoRuntimeError(
            "VIDEO_RUNTIME_FILE_FACT_MISMATCH",
            "generated video file facts do not match storage or ffprobe",
        )
