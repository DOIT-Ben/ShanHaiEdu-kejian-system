"""S3-compatible object storage boundary and MinIO adapter."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Protocol

import certifi
from minio import Minio
from minio.commonconfig import CopySource
from minio.error import S3Error
from urllib3 import PoolManager
from urllib3.exceptions import HTTPError
from urllib3.util import Retry, Timeout

from apps.api.settings import Settings


class ObjectStorageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    bucket: str
    key: str
    etag: str
    size_bytes: int
    media_type: str
    sha256: str | None


class ObjectStorage(Protocol):
    def create_presigned_put(
        self,
        *,
        bucket: str,
        key: str,
        expires: timedelta,
    ) -> str: ...

    def stat(self, *, bucket: str, key: str) -> ObjectMetadata: ...

    def put_bytes(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        media_type: str,
    ) -> ObjectMetadata: ...

    def copy(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
    ) -> ObjectMetadata: ...

    def delete(self, *, bucket: str, key: str) -> None: ...

    def download_to_path(
        self,
        *,
        bucket: str,
        key: str,
        destination: Path,
        max_bytes: int,
    ) -> ObjectMetadata: ...


class MinioObjectStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool,
        create_bucket_if_missing: bool,
        timeout_seconds: float,
    ) -> None:
        http_client = PoolManager(
            timeout=Timeout(connect=timeout_seconds, read=timeout_seconds),
            retries=Retry(total=0),
            cert_reqs="CERT_REQUIRED",
            ca_certs=certifi.where(),
        )
        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            http_client=http_client,
        )
        self._create_bucket_if_missing = create_bucket_if_missing

    def create_presigned_put(
        self,
        *,
        bucket: str,
        key: str,
        expires: timedelta,
    ) -> str:
        try:
            if not self._client.bucket_exists(bucket):
                if not self._create_bucket_if_missing:
                    raise ObjectStorageError("object storage bucket is unavailable")
                self._client.make_bucket(bucket)
            return self._client.presigned_put_object(bucket, key, expires=expires)
        except (S3Error, HTTPError) as exc:
            raise ObjectStorageError("object storage upload session failed") from exc

    def stat(self, *, bucket: str, key: str) -> ObjectMetadata:
        try:
            response = self._client.get_object(bucket, key)
            try:
                hasher = hashlib.sha256()
                while chunk := response.read(64 * 1024):
                    hasher.update(chunk)
                headers = {
                    str(name).lower(): str(value) for name, value in response.headers.items()
                }
            finally:
                response.close()
                response.release_conn()
        except (S3Error, HTTPError) as exc:
            raise ObjectStorageError("object storage object lookup failed") from exc
        etag = headers.get("etag")
        size = headers.get("content-length")
        if etag is None or size is None:
            raise ObjectStorageError("object storage metadata is incomplete")
        return ObjectMetadata(
            bucket=bucket,
            key=key,
            etag=etag.strip('"'),
            size_bytes=int(size),
            media_type=headers.get("content-type", ""),
            sha256=hasher.hexdigest(),
        )

    def put_bytes(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        media_type: str,
    ) -> ObjectMetadata:
        if not payload or not media_type.strip():
            raise ValueError("object storage payload and media type are required")
        try:
            self._ensure_bucket(bucket)
            self._client.put_object(
                bucket,
                key,
                BytesIO(payload),
                len(payload),
                content_type=media_type,
            )
            return self.stat(bucket=bucket, key=key)
        except (S3Error, HTTPError, ObjectStorageError) as exc:
            try:
                self._client.remove_object(bucket, key)
            except (S3Error, HTTPError):
                pass
            raise ObjectStorageError("object storage server-side upload failed") from exc

    def copy(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
    ) -> ObjectMetadata:
        try:
            self._client.copy_object(
                destination_bucket,
                destination_key,
                CopySource(source_bucket, source_key),
            )
            return self.stat(bucket=destination_bucket, key=destination_key)
        except (S3Error, HTTPError, ObjectStorageError) as exc:
            try:
                self._client.remove_object(destination_bucket, destination_key)
            except (S3Error, HTTPError):
                pass
            raise ObjectStorageError("object storage immutable copy failed") from exc

    def delete(self, *, bucket: str, key: str) -> None:
        try:
            self._client.remove_object(bucket, key)
        except (S3Error, HTTPError) as exc:
            raise ObjectStorageError("object storage cleanup failed") from exc

    def download_to_path(
        self,
        *,
        bucket: str,
        key: str,
        destination: Path,
        max_bytes: int,
    ) -> ObjectMetadata:
        if max_bytes <= 0:
            raise ValueError("object storage download limit must be positive")
        response = None
        completed = False
        try:
            response = self._client.get_object(bucket, key)
            headers = {str(name).lower(): str(value) for name, value in response.headers.items()}
            size_header = response.headers.get("content-length")
            if size_header is not None and int(size_header) > max_bytes:
                raise ObjectStorageError("object storage object exceeds download limit")
            bytes_written = 0
            hasher = hashlib.sha256()
            with destination.open("wb") as output:
                while chunk := response.read(64 * 1024):
                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        raise ObjectStorageError("object storage object exceeds download limit")
                    output.write(chunk)
                    hasher.update(chunk)
            completed = True
            return ObjectMetadata(
                bucket=bucket,
                key=key,
                etag=headers.get("etag", "").strip('"'),
                size_bytes=bytes_written,
                media_type=headers.get("content-type", ""),
                sha256=hasher.hexdigest(),
            )
        except ObjectStorageError:
            raise
        except (S3Error, HTTPError, OSError, ValueError) as exc:
            raise ObjectStorageError("object storage download failed") from exc
        finally:
            if response is not None:
                response.close()
                response.release_conn()
            if not completed:
                destination.unlink(missing_ok=True)

    def _ensure_bucket(self, bucket: str) -> None:
        if self._client.bucket_exists(bucket):
            return
        if not self._create_bucket_if_missing:
            raise ObjectStorageError("object storage bucket is unavailable")
        self._client.make_bucket(bucket)


def build_object_storage(settings: Settings) -> ObjectStorage | None:
    if not (
        settings.object_storage_endpoint
        and settings.object_storage_access_key
        and settings.object_storage_secret_key
    ):
        return None
    return MinioObjectStorage(
        endpoint=settings.object_storage_endpoint,
        access_key=settings.object_storage_access_key.get_secret_value(),
        secret_key=settings.object_storage_secret_key.get_secret_value(),
        secure=settings.object_storage_secure,
        create_bucket_if_missing=settings.environment != "production",
        timeout_seconds=settings.dependency_timeout_seconds,
    )
