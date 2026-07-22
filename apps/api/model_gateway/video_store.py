"""Local, non-business storage for explicitly authorized video smokes."""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredVideoFile:
    storage_key: str
    sha256: str
    size_bytes: int
    mime_type: str


class VideoResultStore(Protocol):
    def persist(
        self,
        *,
        key: str,
        source: Path,
        media_type: str,
    ) -> StoredVideoFile: ...


class LocalVideoSmokeStore:
    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root.resolve()

    def persist(
        self,
        *,
        key: str,
        source: Path,
        media_type: str,
    ) -> StoredVideoFile:
        if not source.is_file() or media_type != "video/mp4":
            raise OSError("video smoke output source is invalid")
        destination = self.path_for(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        payload = destination.read_bytes()
        if not payload:
            destination.unlink(missing_ok=True)
            raise OSError("video smoke output is empty")
        return StoredVideoFile(
            storage_key=key,
            sha256=hashlib.sha256(payload).hexdigest(),
            size_bytes=len(payload),
            mime_type=media_type,
        )

    def path_for(self, key: str) -> Path:
        relative = PurePosixPath(key)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise OSError("video smoke output key is unsafe")
        destination = (self._output_root / Path(*relative.parts)).resolve()
        try:
            destination.relative_to(self._output_root)
        except ValueError as exc:
            raise OSError("video smoke output key escapes the output root") from exc
        return destination
