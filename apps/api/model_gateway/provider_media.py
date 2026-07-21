"""Materialize one validated private image for a provider-only HTTPS relay."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from apps.api.assets.provider_media import ProviderMediaAssetReader, ProviderMediaAssetVersion
from apps.api.model_gateway.contracts import MediaReference
from apps.api.provider_media_relay import sign_media_path
from apps.api.uploads.storage import ObjectStorage, ObjectStorageError

_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
_OPAQUE_FILENAME = re.compile(r"[0-9a-f]{32}\.(?:png|jpg|webp)", re.ASCII)
_MAX_PROVIDER_URL_LENGTH = 4096


class ProviderMediaResolutionError(ValueError):
    """Raised when an internal reference cannot become provider transport media."""


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
        if not self.signing_secret:
            raise ValueError("signing_secret must not be empty")
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
            written = self._storage.download_to_path(
                bucket=asset.storage_bucket,
                key=asset.storage_key,
                destination=temporary,
                max_bytes=self._config.max_file_bytes,
            )
            self._validate_download(temporary, asset, written)
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
        cutoff = (time.time() if now is None else now) - self._config.ttl_seconds
        removed = 0
        for candidate in self._config.relay_root.iterdir():
            if not _OPAQUE_FILENAME.fullmatch(candidate.name) or candidate.is_symlink():
                continue
            try:
                if candidate.is_file() and candidate.stat().st_mtime <= cutoff:
                    candidate.unlink()
                    removed += 1
            except OSError:
                continue
        return removed

    def _validate_reference(
        self,
        asset: ProviderMediaAssetVersion,
        organization_id: UUID,
        reference: MediaReference,
    ) -> None:
        if (
            asset.id != reference.file_version_id
            or asset.organization_id != organization_id
            or asset.mime_type != reference.mime_type
            or asset.mime_type not in _MIME_EXTENSIONS
            or not 0 < asset.byte_size <= self._config.max_file_bytes
        ):
            raise ProviderMediaResolutionError("provider media reference is invalid")

    def _temporary_path(self) -> Path:
        descriptor, raw_path = tempfile.mkstemp(
            dir=self._config.relay_root,
            prefix=".provider-media-",
            suffix=".partial",
        )
        os.close(descriptor)
        return Path(raw_path)

    def _validate_download(
        self,
        path: Path,
        asset: ProviderMediaAssetVersion,
        written: int,
    ) -> None:
        content = path.read_bytes()
        size = len(content)
        digest = hashlib.sha256(content).hexdigest()
        if (
            written != asset.byte_size
            or size != asset.byte_size
            or digest != asset.sha256
            or _detect_media_type(content) != asset.mime_type
        ):
            raise ProviderMediaResolutionError("provider media object failed integrity validation")

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


def _detect_media_type(content: bytes) -> str | None:
    header = content[:12]
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None
