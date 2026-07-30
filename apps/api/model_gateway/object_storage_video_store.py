from __future__ import annotations

import hashlib
from pathlib import Path

from apps.api.model_gateway.video_store import StoredVideoFile
from apps.api.uploads.storage import ObjectStorage, ObjectStorageError


class ObjectStorageVideoResultStore:
    def __init__(
        self,
        storage: ObjectStorage,
        *,
        bucket: str,
        max_bytes: int,
    ) -> None:
        self._storage = storage
        self._bucket = bucket
        self._max_bytes = max_bytes

    def persist(
        self,
        *,
        key: str,
        source: Path,
        media_type: str,
    ) -> StoredVideoFile:
        if media_type != "video/mp4" or not source.is_file():
            raise OSError("video result source is invalid")
        size = source.stat().st_size
        if size <= 0 or size > self._max_bytes:
            raise OSError("video result size is invalid")
        payload = source.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        try:
            metadata = self._storage.put_bytes(
                bucket=self._bucket,
                key=key,
                payload=payload,
                media_type=media_type,
            )
        except ObjectStorageError as exc:
            raise OSError("video result storage failed") from exc
        if (
            metadata.media_type != media_type
            or metadata.size_bytes != size
            or metadata.sha256 != digest
        ):
            try:
                self._storage.delete(bucket=self._bucket, key=key)
            except ObjectStorageError:
                pass
            raise OSError("stored video result facts do not match")
        return StoredVideoFile(
            storage_key=key,
            sha256=digest,
            size_bytes=size,
            mime_type=media_type,
        )
