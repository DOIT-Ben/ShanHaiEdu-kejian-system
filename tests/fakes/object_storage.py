from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from apps.api.uploads.storage import ObjectMetadata, ObjectNotFoundError, ObjectStorageError


@dataclass(frozen=True, slots=True)
class PresignedPut:
    bucket: str
    key: str
    expires: timedelta


class FakeObjectStorage:
    def __init__(self) -> None:
        self.last_presigned: PresignedPut | None = None
        self.presigned_requests: list[PresignedPut] = []
        self._objects: dict[tuple[str, str], ObjectMetadata] = {}
        self._payloads: dict[tuple[str, str], bytes] = {}

    @property
    def object_count(self) -> int:
        return len(self._objects)

    def create_presigned_put(
        self,
        *,
        bucket: str,
        key: str,
        expires: timedelta,
    ) -> str:
        self.last_presigned = PresignedPut(bucket=bucket, key=key, expires=expires)
        self.presigned_requests.append(self.last_presigned)
        return f"https://object-storage.test/{bucket}/{key}?signature=fake"

    def stat(self, *, bucket: str, key: str) -> ObjectMetadata:
        try:
            return self._objects[(bucket, key)]
        except KeyError as exc:
            raise ObjectNotFoundError("fake object not found") from exc

    def put(self, metadata: ObjectMetadata) -> None:
        self._objects[(metadata.bucket, metadata.key)] = metadata

    def put_bytes(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        media_type: str,
    ) -> ObjectMetadata:
        digest = hashlib.sha256(payload).hexdigest()
        metadata = ObjectMetadata(
            bucket=bucket,
            key=key,
            etag=digest,
            size_bytes=len(payload),
            media_type=media_type,
            sha256=digest,
            last_modified=datetime.now(UTC),
        )
        self._objects[(bucket, key)] = metadata
        self._payloads[(bucket, key)] = payload
        return metadata

    def put_at(self, *, bucket: str, key: str, metadata: ObjectMetadata) -> None:
        self._objects[(bucket, key)] = metadata

    def copy(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
    ) -> ObjectMetadata:
        source = self.stat(bucket=source_bucket, key=source_key)
        copied = replace(source, bucket=destination_bucket, key=destination_key)
        self.put(copied)
        payload = self._payloads.get((source_bucket, source_key))
        if payload is not None:
            self._payloads[(destination_bucket, destination_key)] = payload
        return copied

    def delete(self, *, bucket: str, key: str) -> None:
        self._objects.pop((bucket, key), None)
        self._payloads.pop((bucket, key), None)

    def list_objects(
        self,
        *,
        bucket: str,
        prefix: str,
        limit: int,
    ) -> list[ObjectMetadata]:
        objects = [
            metadata
            for (object_bucket, key), metadata in self._objects.items()
            if object_bucket == bucket and key.startswith(prefix)
        ]
        return sorted(
            objects,
            key=lambda item: (
                item.last_modified.timestamp() if item.last_modified is not None else float("inf"),
                item.key,
            ),
        )[:limit]

    def download_to_path(
        self,
        *,
        bucket: str,
        key: str,
        destination: Path,
        max_bytes: int,
    ) -> ObjectMetadata:
        try:
            payload = self._payloads[(bucket, key)]
        except KeyError as exc:
            raise ObjectStorageError("fake object payload not found") from exc
        if len(payload) > max_bytes:
            raise ObjectStorageError("fake object exceeds download limit")
        destination.write_bytes(payload)
        metadata = self._objects[(bucket, key)]
        return replace(
            metadata,
            size_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
