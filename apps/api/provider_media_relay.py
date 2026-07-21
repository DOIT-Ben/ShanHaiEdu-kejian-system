"""Constrained localhost relay for one provider-readable image at a time."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import logging
import os
import re
import stat
import time
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, quote, urlencode, urlsplit

logger = logging.getLogger(__name__)

_ALLOWED_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_FILENAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}", re.ASCII)
_MAX_EXPIRY_DIGITS = 20
_LOOPBACK_HOST = "127.0.0.1"


class ProviderMediaRequestError(ValueError):
    """Raised when a provider-media request violates the relay boundary."""


@dataclass(frozen=True, slots=True)
class ProviderMediaRelayConfig:
    root: Path
    signing_secret: str
    max_ttl_seconds: int
    max_file_bytes: int

    def __post_init__(self) -> None:
        if not self.signing_secret:
            raise ValueError("signing_secret must not be empty")
        if not 1 <= self.max_ttl_seconds <= 3_600:
            raise ValueError("max_ttl_seconds must be between 1 and 3600")
        if self.max_file_bytes < 1:
            raise ValueError("max_file_bytes must be positive")
        object.__setattr__(self, "root", self.root.resolve())


@dataclass(frozen=True, slots=True)
class ProviderMediaAsset:
    path: Path
    media_type: str
    size_bytes: int
    content: bytes


def sign_media_path(filename: str, *, expires_at: int, secret: str) -> str:
    """Return a relative signed path for a controlled relay file.

    This helper is for trusted server-side callers only. It intentionally returns
    no hostname so the caller must select the provider-facing HTTPS origin.
    """

    _require_safe_filename(filename)
    if expires_at <= 0:
        raise ValueError("expires_at must be positive")
    if not secret:
        raise ValueError("secret must not be empty")
    expires = str(expires_at)
    signature = _signature_for(filename, expires, secret)
    return f"/{quote(filename, safe='')}?{urlencode({'expires': expires, 'signature': signature})}"


def resolve_media_request(
    request_path: str,
    config: ProviderMediaRelayConfig,
    *,
    now: int | None = None,
) -> ProviderMediaAsset:
    """Validate a signed request path and return exactly one local image asset."""

    filename, expires, signature = _parse_signed_path(request_path)
    current_time = int(time.time()) if now is None else now
    if expires < current_time or expires - current_time > config.max_ttl_seconds:
        raise ProviderMediaRequestError("expired or excessively long-lived request")
    expected_signature = _signature_for(filename, str(expires), config.signing_secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise ProviderMediaRequestError("invalid request signature")

    expected_media_type = _ALLOWED_MEDIA_TYPES.get(Path(filename).suffix.lower())
    if expected_media_type is None:
        raise ProviderMediaRequestError("media type is not allowed")
    content = _read_media_content(config.root, filename, config.max_file_bytes)
    if _detect_media_type(content) != expected_media_type:
        raise ProviderMediaRequestError("media bytes do not match the declared type")
    return ProviderMediaAsset(
        path=config.root / filename,
        media_type=expected_media_type,
        size_bytes=len(content),
        content=content,
    )


class ProviderMediaRelayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int, config: ProviderMediaRelayConfig) -> None:
        super().__init__((_LOOPBACK_HOST, port), ProviderMediaRequestHandler)
        self.config = config


class ProviderMediaRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send_health()
            return
        try:
            relay_server = cast(ProviderMediaRelayServer, self.server)
            asset = resolve_media_request(self.path, relay_server.config)
        except ProviderMediaRequestError:
            self._send_not_found()
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", asset.media_type)
        self.send_header("Content-Length", str(asset.size_bytes))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        try:
            self.wfile.write(asset.content)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_HEAD(self) -> None:
        self._send_not_found()

    def log_message(self, format: str, *args: object) -> None:
        """Never log request targets because their query contains a signature."""

    def _send_health(self) -> None:
        body = b"ok\n"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_not_found(self) -> None:
        self.send_response(HTTPStatus.NOT_FOUND)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


def build_relay_config(environ: Mapping[str, str] | None = None) -> ProviderMediaRelayConfig:
    values = os.environ if environ is None else environ
    root = _required_environment_value(values, "SHANHAI_PROVIDER_MEDIA_ROOT")
    secret = _required_environment_value(values, "SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET")
    return ProviderMediaRelayConfig(
        root=Path(root),
        signing_secret=secret,
        max_ttl_seconds=_environment_int(values, "SHANHAI_PROVIDER_MEDIA_MAX_TTL_SECONDS", 300),
        max_file_bytes=_environment_int(
            values, "SHANHAI_PROVIDER_MEDIA_MAX_FILE_BYTES", 10_485_760
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="serve short-lived provider media references")
    parser.add_argument("--port", type=int, default=8201)
    args = parser.parse_args()
    if not 1 <= args.port <= 65_535:
        parser.error("--port must be between 1 and 65535")
    server = ProviderMediaRelayServer(args.port, build_relay_config())
    logger.info("provider_media_relay_started", extra={"host": _LOOPBACK_HOST, "port": args.port})
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _parse_signed_path(request_path: str) -> tuple[str, int, str]:
    parsed = urlsplit(request_path)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ProviderMediaRequestError("request target must be a relative path")
    if not parsed.path.startswith("/") or parsed.path.count("/") != 1:
        raise ProviderMediaRequestError("request path must contain exactly one filename")
    filename = parsed.path.removeprefix("/")
    _require_safe_filename(filename)
    try:
        values = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError as error:
        raise ProviderMediaRequestError("invalid request query") from error
    if set(values) != {"expires", "signature"} or any(len(value) != 1 for value in values.values()):
        raise ProviderMediaRequestError("request query must contain one expiry and signature")
    expires_text = values["expires"][0]
    signature = values["signature"][0]
    if (
        not expires_text.isascii()
        or not expires_text.isdecimal()
        or len(expires_text) > _MAX_EXPIRY_DIGITS
    ):
        raise ProviderMediaRequestError("invalid expiry")
    if not re.fullmatch(r"[0-9a-f]{64}", signature, re.ASCII):
        raise ProviderMediaRequestError("invalid signature")
    return filename, int(expires_text), signature


def _require_safe_filename(filename: str) -> None:
    if not _FILENAME_PATTERN.fullmatch(filename):
        raise ProviderMediaRequestError("unsafe media filename")


def _signature_for(filename: str, expires: str, secret: str) -> str:
    payload = f"v1\n{filename}\n{expires}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _read_media_content(root: Path, filename: str, max_file_bytes: int) -> bytes:
    try:
        descriptor = _open_media_descriptor(root, filename)
    except OSError as error:
        raise ProviderMediaRequestError("media file is unavailable") from error
    try:
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise ProviderMediaRequestError("media target is not a regular file")
            if metadata.st_size > max_file_bytes:
                raise ProviderMediaRequestError("media file exceeds configured size")
            content = stream.read(max_file_bytes + 1)
    except OSError as error:
        raise ProviderMediaRequestError("media file cannot be read") from error
    if len(content) != metadata.st_size or len(content) > max_file_bytes:
        raise ProviderMediaRequestError("media file changed while being read")
    return content


def _open_media_descriptor(root: Path, filename: str) -> int:
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if os.name == "nt":
        return os.open(root / filename, file_flags)

    root_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    root_descriptor = os.open(root, root_flags)
    try:
        return os.open(filename, file_flags, dir_fd=root_descriptor)
    finally:
        os.close(root_descriptor)


def _detect_media_type(content: bytes) -> str | None:
    header = content[:12]
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def _required_environment_value(values: Mapping[str, str], name: str) -> str:
    value = values.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _environment_int(values: Mapping[str, str], name: str, default: int) -> int:
    value = values.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error


if __name__ == "__main__":
    raise SystemExit(main())
