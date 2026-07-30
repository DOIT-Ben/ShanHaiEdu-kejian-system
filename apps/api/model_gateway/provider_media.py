"""Materialize one validated private image for a provider-only HTTPS relay."""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from apps.api.assets.provider_media import ProviderMediaAssetReader, ProviderMediaAssetVersion
from apps.api.model_gateway.contracts import MediaReference
from apps.api.provider_media_relay import (
    cleanup_expired_provider_media,
    sign_media_path,
    validate_provider_media_signing_secret,
)
from apps.api.uploads.storage import ObjectMetadata, ObjectStorage, ObjectStorageError

_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
_MAX_PROVIDER_URL_LENGTH = 4096


class ProviderMediaResolutionError(ValueError):
    """Raised when an internal reference cannot become provider transport media."""


@dataclass(frozen=True, slots=True)
class ProviderMediaBlob:
    content: bytes
    mime_type: str
    sha256: str

    @property
    def size_bytes(self) -> int:
        return len(self.content)


class ProviderMediaReferenceReader:
    """Reads one validated tenant-scoped image without creating a public URL."""

    def __init__(
        self,
        *,
        asset_reader: ProviderMediaAssetReader,
        storage: ObjectStorage,
        max_file_bytes: int,
    ) -> None:
        if max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")
        self._asset_reader = asset_reader
        self._storage = storage
        self._max_file_bytes = max_file_bytes

    def read(self, *, organization_id: UUID, reference: MediaReference) -> ProviderMediaBlob:
        asset = self._asset_reader.get_clean_image_version(
            organization_id=organization_id,
            file_version_id=reference.file_version_id,
        )
        if asset is None:
            raise ProviderMediaResolutionError("provider media asset is unavailable")
        _validate_provider_media_reference(
            asset,
            organization_id,
            reference,
            max_file_bytes=self._max_file_bytes,
        )
        descriptor, temporary = tempfile.mkstemp(
            prefix="shanhaiedu-provider-media-",
            suffix=".partial",
        )
        os.close(descriptor)
        path = Path(temporary)
        try:
            downloaded = self._storage.download_to_path(
                bucket=asset.storage_bucket,
                key=asset.storage_key,
                destination=path,
                max_bytes=self._max_file_bytes,
            )
            _validate_provider_media_download(path, asset, downloaded)
            content = path.read_bytes()
            return ProviderMediaBlob(
                content=content,
                mime_type=asset.mime_type,
                sha256=asset.sha256,
            )
        except (OSError, ObjectStorageError) as error:
            raise ProviderMediaResolutionError("provider media object is unavailable") from error
        finally:
            path.unlink(missing_ok=True)


@dataclass(frozen=True, slots=True)
class ProviderMediaResolverConfig:
    relay_root: Path
    public_base_url: str
    signing_secret: str
    ttl_seconds: int
    max_file_bytes: int

    def __post_init__(self) -> None:
        root = self.relay_root.resolve()
        if not root.is_dir():
            raise ValueError("relay_root must be an existing directory")
        validate_provider_media_signing_secret(self.signing_secret)
        if not 1 <= self.ttl_seconds <= 3_600:
            raise ValueError("ttl_seconds must be between 1 and 3600")
        if self.max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")
        parsed = urlsplit(self.public_base_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("public_base_url must be a plain HTTPS origin and path")
        object.__setattr__(self, "relay_root", root)
        object.__setattr__(self, "public_base_url", self.public_base_url.rstrip("/"))


class ProviderMediaReferenceResolver:
    """Creates an ephemeral provider URL without exposing it to product surfaces."""

    def __init__(
        self,
        *,
        asset_reader: ProviderMediaAssetReader,
        storage: ObjectStorage,
        config: ProviderMediaResolverConfig,
    ) -> None:
        self._asset_reader = asset_reader
        self._storage = storage
        self._config = config

    def resolve(self, *, organization_id: UUID, reference: MediaReference) -> str:
        self.cleanup_expired()
        asset = self._asset_reader.get_clean_image_version(
            organization_id=organization_id,
            file_version_id=reference.file_version_id,
        )
        if asset is None:
            raise ProviderMediaResolutionError("provider media asset is unavailable")
        self._validate_reference(asset, organization_id, reference)
        destination = self._config.relay_root / self._filename_for(asset.mime_type)
        temporary = self._temporary_path()
        try:
            downloaded = self._storage.download_to_path(
                bucket=asset.storage_bucket,
                key=asset.storage_key,
                destination=temporary,
                max_bytes=self._config.max_file_bytes,
            )
            self._validate_download(temporary, asset, downloaded)
            os.chmod(temporary, 0o640)
            os.replace(temporary, destination)
        except (OSError, ObjectStorageError) as error:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise ProviderMediaResolutionError("provider media object is unavailable") from error
        except ProviderMediaResolutionError:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        try:
            return self._signed_url(destination.name)
        except ProviderMediaResolutionError:
            destination.unlink(missing_ok=True)
            raise

    def cleanup_expired(self, *, now: float | None = None) -> int:
        return cleanup_expired_provider_media(
            self._config.relay_root,
            ttl_seconds=self._config.ttl_seconds,
            now=now,
        )

    def _validate_reference(
        self,
        asset: ProviderMediaAssetVersion,
        organization_id: UUID,
        reference: MediaReference,
    ) -> None:
        _validate_provider_media_reference(
            asset,
            organization_id,
            reference,
            max_file_bytes=self._config.max_file_bytes,
        )

    def _temporary_path(self) -> Path:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        for _attempt in range(3):
            path = self._config.relay_root / f".provider-media-{uuid4().hex}.partial"
            try:
                descriptor = os.open(path, flags, 0o600)
            except FileExistsError:
                continue
            os.close(descriptor)
            return path
        raise ProviderMediaResolutionError("provider media temporary file is unavailable")

    def _validate_download(
        self,
        path: Path,
        asset: ProviderMediaAssetVersion,
        downloaded: ObjectMetadata,
    ) -> None:
        _validate_provider_media_download(path, asset, downloaded)

    def _filename_for(self, mime_type: str) -> str:
        return f"{uuid4().hex}{_MIME_EXTENSIONS[mime_type]}"

    def _signed_url(self, filename: str) -> str:
        expires_at = int(time.time()) + self._config.ttl_seconds
        path = sign_media_path(
            filename,
            expires_at=expires_at,
            secret=self._config.signing_secret,
        )
        url = f"{self._config.public_base_url}{path}"
        if len(url) > _MAX_PROVIDER_URL_LENGTH:
            raise ProviderMediaResolutionError("provider media URL exceeds the provider limit")
        return url


def _validate_provider_media_reference(
    asset: ProviderMediaAssetVersion,
    organization_id: UUID,
    reference: MediaReference,
    *,
    max_file_bytes: int,
) -> None:
    if (
        asset.id != reference.file_version_id
        or asset.organization_id != organization_id
        or asset.mime_type != reference.mime_type
        or asset.mime_type not in _MIME_EXTENSIONS
        or not 0 < asset.byte_size <= max_file_bytes
    ):
        raise ProviderMediaResolutionError("provider media reference is invalid")


def _validate_provider_media_download(
    path: Path,
    asset: ProviderMediaAssetVersion,
    downloaded: ObjectMetadata,
) -> None:
    content = path.read_bytes()
    size = len(content)
    digest = hashlib.sha256(content).hexdigest()
    if (
        downloaded.bucket != asset.storage_bucket
        or downloaded.key != asset.storage_key
        or downloaded.size_bytes != asset.byte_size
        or _normalized_media_type(downloaded.media_type) != asset.mime_type
        or downloaded.sha256 != asset.sha256
        or size != asset.byte_size
        or digest != asset.sha256
        or _detect_media_type(content) != asset.mime_type
    ):
        raise ProviderMediaResolutionError("provider media object failed integrity validation")


def _detect_media_type(content: bytes) -> str | None:
    header = content[:12]
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _normalized_media_type(value: str) -> str:
    return value.split(";", 1)[0].strip().lower()
