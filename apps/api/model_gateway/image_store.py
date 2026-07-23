"""Local, non-business object storage for explicitly authorized image smokes."""

from __future__ import annotations

import hashlib
import shutil
from datetime import timedelta
from pathlib import Path, PurePosixPath

from apps.api.uploads.storage import ObjectMetadata, ObjectStorageError


class LocalImageSmokeStorage:
    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root.resolve()

    def create_presigned_put(
        self,
        *,
        bucket: str,
        key: str,
        expires: timedelta,
    ) -> str:
        raise ObjectStorageError("image smoke storage does not support presigned uploads")

    def stat(self, *, bucket: str, key: str) -> ObjectMetadata:
        path = self.path_for(bucket=bucket, key=key)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ObjectStorageError("image smoke object lookup failed") from exc
        return self._metadata(bucket=bucket, key=key, payload=payload)

    def put_bytes(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        media_type: str,
    ) -> ObjectMetadata:
        if not payload or media_type != "image/png":
            raise ObjectStorageError("image smoke payload must be a non-empty PNG")
        destination = self.path_for(bucket=bucket, key=key)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        except OSError as exc:
            destination.unlink(missing_ok=True)
            raise ObjectStorageError("image smoke object write failed") from exc
        return self._metadata(bucket=bucket, key=key, payload=payload)

    def copy(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
    ) -> ObjectMetadata:
        source = self.path_for(bucket=source_bucket, key=source_key)
        destination = self.path_for(bucket=destination_bucket, key=destination_key)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        except OSError as exc:
            destination.unlink(missing_ok=True)
            raise ObjectStorageError("image smoke object copy failed") from exc
        return self.stat(bucket=destination_bucket, key=destination_key)

    def delete(self, *, bucket: str, key: str) -> None:
        try:
            self.path_for(bucket=bucket, key=key).unlink(missing_ok=True)
        except OSError as exc:
            raise ObjectStorageError("image smoke object cleanup failed") from exc

    def download_to_path(
        self,
        *,
        bucket: str,
        key: str,
        destination: Path,
        max_bytes: int,
    ) -> ObjectMetadata:
        metadata = self.stat(bucket=bucket, key=key)
        if metadata.size_bytes > max_bytes:
            raise ObjectStorageError("image smoke object exceeds download limit")
        try:
            shutil.copyfile(self.path_for(bucket=bucket, key=key), destination)
        except OSError as exc:
            destination.unlink(missing_ok=True)
            raise ObjectStorageError("image smoke object download failed") from exc
        return metadata

    def path_for(self, *, bucket: str, key: str) -> Path:
        if not bucket or any(character in bucket for character in "/\\"):
            raise ObjectStorageError("image smoke bucket is unsafe")
        relative = PurePosixPath(key)
        if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
            raise ObjectStorageError("image smoke object key is unsafe")
        destination = (self._output_root / bucket / Path(*relative.parts)).resolve()
        try:
            destination.relative_to(self._output_root)
        except ValueError as exc:
            raise ObjectStorageError("image smoke object key escapes output root") from exc
        return destination

    @staticmethod
    def _metadata(*, bucket: str, key: str, payload: bytes) -> ObjectMetadata:
        digest = hashlib.sha256(payload).hexdigest()
        return ObjectMetadata(
            bucket=bucket,
            key=key,
            etag=digest,
            size_bytes=len(payload),
            media_type="image/png",
            sha256=digest,
        )
