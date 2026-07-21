from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from apps.api.provider_media_relay import (
    ProviderMediaRelayConfig,
    ProviderMediaRelayServer,
    ProviderMediaRequestError,
    resolve_media_request,
    sign_media_path,
)

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADElEQVR42mNk+M/wHwAF/gL+3MxZ5wAAAABJRU5ErkJggg=="
)
VALID_SIGNING_SECRET = hashlib.sha256(b"provider-media-relay-test").hexdigest()


def relay_config(root: Path, *, max_file_bytes: int = 1_024) -> ProviderMediaRelayConfig:
    return ProviderMediaRelayConfig(
        root=root,
        signing_secret=VALID_SIGNING_SECRET,
        max_ttl_seconds=300,
        max_file_bytes=max_file_bytes,
    )


@pytest.mark.parametrize(
    "secret",
    [
        "",
        "a1" * 31 + "a",
        "a1" * 32 + "a",
        "g1" * 32,
        "a" * 64,
        "0123456789abcdef" * 4,
        "PLACEHOLDER_REPLACE_WITH_A_UNIQUE_64_HEX_CHARACTER_SECRET",
    ],
)
def test_relay_rejects_invalid_signing_secret_without_disclosure(
    tmp_path: Path,
    secret: str,
) -> None:
    with pytest.raises(ValueError) as error:
        ProviderMediaRelayConfig(
            root=tmp_path,
            signing_secret=secret,
            max_ttl_seconds=300,
            max_file_bytes=1_024,
        )

    assert "signing_secret is invalid" in str(error.value)
    if secret:
        assert secret not in str(error.value)

    with pytest.raises(ValueError, match="signing_secret is invalid") as signing_error:
        sign_media_path("frame.png", expires_at=1_100, secret=secret)
    if secret:
        assert secret not in str(signing_error.value)


def test_relay_accepts_mixed_case_64_hex_secret_without_normalizing(tmp_path: Path) -> None:
    secret = "Aa1b" * 16

    config = ProviderMediaRelayConfig(
        root=tmp_path,
        signing_secret=secret,
        max_ttl_seconds=300,
        max_file_bytes=1_024,
    )

    assert config.signing_secret == secret


def test_valid_signed_image_resolves_to_a_private_file(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(PNG_BYTES)
    config = relay_config(tmp_path)
    path = sign_media_path("frame.png", expires_at=1_100, secret=config.signing_secret)

    asset = resolve_media_request(path, config, now=1_000)

    assert asset.path == image
    assert asset.media_type == "image/png"
    assert asset.size_bytes == len(PNG_BYTES)
    assert asset.content == PNG_BYTES


@pytest.mark.parametrize(
    "path",
    [
        "/frame.png?expires=999&signature=ignored",
        "/frame.png?expires=1301&signature=ignored",
        "/../secret.png?expires=1100&signature=ignored",
    ],
)
def test_invalid_expiry_or_unsafe_path_fails_closed(tmp_path: Path, path: str) -> None:
    config = relay_config(tmp_path)

    with pytest.raises(ProviderMediaRequestError):
        resolve_media_request(path, config, now=1_000)


def test_tampered_signature_fails_closed(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(PNG_BYTES)
    config = relay_config(tmp_path)
    path = sign_media_path("frame.png", expires_at=1_100, secret=config.signing_secret)
    tampered = path.replace("signature=", "signature=altered")

    with pytest.raises(ProviderMediaRequestError):
        resolve_media_request(tampered, config, now=1_000)


def test_non_image_and_oversized_files_fail_closed(tmp_path: Path) -> None:
    text_file = tmp_path / "frame.txt"
    text_file.write_text("not an image", encoding="utf-8")
    large_image = tmp_path / "large.png"
    large_image.write_bytes(PNG_BYTES + b"x" * 20)
    config = relay_config(tmp_path, max_file_bytes=10)

    for filename in ("frame.txt", "large.png"):
        path = sign_media_path(filename, expires_at=1_100, secret=config.signing_secret)
        with pytest.raises(ProviderMediaRequestError):
            resolve_media_request(path, config, now=1_000)


def test_extension_must_match_detected_image_type(tmp_path: Path) -> None:
    disguised_image = tmp_path / "frame.jpg"
    disguised_image.write_bytes(PNG_BYTES)
    config = relay_config(tmp_path)
    path = sign_media_path("frame.jpg", expires_at=1_100, secret=config.signing_secret)

    with pytest.raises(ProviderMediaRequestError):
        resolve_media_request(path, config, now=1_000)


def test_symlink_to_file_outside_relay_root_fails_closed(tmp_path: Path) -> None:
    external_image = tmp_path.parent / "provider-media-relay-external.png"
    external_image.write_bytes(PNG_BYTES)
    linked_image = tmp_path / "frame.png"
    try:
        linked_image.symlink_to(external_image)
    except OSError:
        external_image.unlink()
        pytest.skip("symbolic links require a Windows developer privilege")
    config = relay_config(tmp_path)
    path = sign_media_path("frame.png", expires_at=1_100, secret=config.signing_secret)

    try:
        with pytest.raises(ProviderMediaRequestError):
            resolve_media_request(path, config, now=1_000)
    finally:
        external_image.unlink()


def test_http_relay_serves_valid_image_without_caching(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(PNG_BYTES)
    config = relay_config(tmp_path)
    server = ProviderMediaRelayServer(0, config)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    path = sign_media_path(
        "frame.png",
        expires_at=int(__import__("time").time()) + 30,
        secret=config.signing_secret,
    )
    host = str(server.server_address[0])
    port = int(server.server_address[1])
    assert host == "127.0.0.1"

    try:
        with urlopen(f"http://{host}:{port}{path}") as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "image/png"
            assert response.headers["Cache-Control"] == "no-store"
            assert response.read() == PNG_BYTES
        with pytest.raises(HTTPError) as response:
            urlopen(f"http://{host}:{port}{path}x")
        assert response.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_expired_media_cleanup_is_scheduled_independently() -> None:
    root = Path(__file__).resolve().parents[2]
    relay_service = (root / "infra/provider-media-relay/provider-media-relay.service").read_text(
        encoding="utf-8"
    )
    service = (root / "infra/provider-media-relay/provider-media-cleanup.service").read_text(
        encoding="utf-8"
    )
    timer = (root / "infra/provider-media-relay/provider-media-cleanup.timer").read_text(
        encoding="utf-8"
    )

    cleanup_env = (
        root / "infra/provider-media-relay/provider-media-cleanup.env.example"
    ).read_text(encoding="utf-8")
    relay_env = (root / "infra/provider-media-relay/provider-media-relay.env.example").read_text(
        encoding="utf-8"
    )
    runbook = (root / "infra/provider-media-relay/README.md").read_text(encoding="utf-8")

    assert "User=shanhai-relay" in relay_service
    assert "User=shanhai-dev" not in relay_service
    assert "/opt/shanhaiedu/provider-media-relay/provider_media_relay.py" in relay_service
    assert "/srv/shanhaiedu/repository" not in relay_service
    assert "provider-media-cleanup.env" in service
    assert "provider-media-relay.env" not in service
    assert "SIGNING_SECRET" not in cleanup_env
    assert "SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET=" not in relay_env
    assert "ReadWritePaths=/srv/shanhaiedu/runtime/provider-media" in service
    assert "OnUnitActiveSec=60s" in timer
    assert "Persistent=true" in timer
    assert "systemctl restart shanhai-provider-media-relay.service" in runbook
    assert "/proc/${relay_pid}/environ" in runbook
    assert "git rev-parse origin/main" in runbook
    assert "sha256sum apps/api/provider_media_relay.py" in runbook
    assert "sha256sum /opt/shanhaiedu/provider-media-relay/provider_media_relay.py" in runbook
    assert "date -u +%Y-%m-%dT%H:%M:%SZ" in runbook
