from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from apps.api.provider_media_relay import (
    ProviderMediaRelayConfig,
    ProviderMediaRelayServer,
    ProviderMediaRequestError,
    cleanup_expired_provider_media,
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


def test_standalone_cleanup_needs_no_signing_secret(tmp_path: Path) -> None:
    stale = tmp_path / f"{'a' * 32}.png"
    stale.write_bytes(PNG_BYTES)
    os.utime(stale, (time.time() - 61, time.time() - 61))
    unrelated = tmp_path / "operator-note.txt"
    unrelated.write_text("preserve", encoding="utf-8")
    script = Path(__file__).resolve().parents[2] / "apps/api/provider_media_relay.py"
    environment = os.environ.copy()
    environment["SHANHAI_PROVIDER_MEDIA_ROOT"] = str(tmp_path)
    environment["SHANHAI_PROVIDER_MEDIA_MAX_TTL_SECONDS"] = "60"
    environment.pop("SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET", None)

    completed = subprocess.run(
        [sys.executable, "-I", str(script), "--cleanup"],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert json.loads(completed.stdout) == {"conclusion": "passed", "removed": 1}
    assert not stale.exists()
    assert unrelated.read_text(encoding="utf-8") == "preserve"


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
    assert "WorkingDirectory=/opt/shanhaiedu/provider-media-relay" in service
    assert (
        "ExecStart=/usr/bin/python3 "
        "/opt/shanhaiedu/provider-media-relay/provider_media_relay.py --cleanup"
    ) in service
    assert "/srv/shanhaiedu/repository/.venv" not in service
    assert "ReadWritePaths=/srv/shanhaiedu/runtime/provider-media" in service
    assert "OnUnitActiveSec=60s" in timer
    assert "Persistent=true" in timer
    assert "systemctl restart shanhai-provider-media-relay.service" in runbook
    assert "/proc/${relay_pid}/environ" in runbook
    assert 'git -C "${repository_root}" rev-parse origin/main' in runbook
    assert 'sha256sum "${relay_staging}"' in runbook
    assert "sha256sum /opt/shanhaiedu/provider-media-relay/provider_media_relay.py" in runbook
    assert "date -u +%Y-%m-%dT%H:%M:%SZ" in runbook


def test_relay_deploy_provenance_fails_closed_before_mutation() -> None:
    root = Path(__file__).resolve().parents[2]
    runbook = (root / "infra/provider-media-relay/README.md").read_text(encoding="utf-8")
    fetch = 'sudo -u shanhai-dev -H git -C "${repository_root}" fetch origin --prune'
    staged_blob = (
        'git -C "${repository_root}" show '
        '"${deployment_origin_main_sha}:apps/api/provider_media_relay.py" '
        '> "${relay_staging}"'
    )
    relay_install = (
        'install -m 0555 -o root -g root "${relay_staging}" '
        "/opt/shanhaiedu/provider-media-relay/provider_media_relay.py"
    )
    installed_blob_check = (
        'cmp --silent "${relay_staging}" '
        "/opt/shanhaiedu/provider-media-relay/provider_media_relay.py"
    )
    first_mutation = runbook.index("id -u shanhai-relay")
    first_install = runbook.index("install -d -m 0755")
    restart = runbook.index("systemctl restart shanhai-provider-media-relay.service")

    assert runbook.index("set -euo pipefail") < runbook.index(fetch)
    assert runbook.index(fetch) < runbook.index(staged_blob) < first_mutation < first_install
    assert runbook.index(relay_install) < runbook.index(installed_blob_check) < restart
    assert 'test "${relay_staged_sha256}" = "${relay_blob_sha256}"' in runbook
    assert 'test "${relay_installed_sha256}" = "${relay_blob_sha256}"' in runbook
    assert 'test "$(git rev-parse HEAD)"' not in runbook
    assert "/srv/shanhaiedu/repository/.venv/bin/python" not in runbook
    assert "/etc/shanhaiedu/image-video-smoke.env" in runbook
    assert 'old_url="$(cd "${deployment_staging}"' in runbook
    assert "provider-media-cleanup-keep.txt" in runbook
    assert "journalctl -u shanhai-provider-media-relay.service" in runbook


def test_cleanup_contract_is_shared_by_runtime_and_model_gateway(tmp_path: Path) -> None:
    stale = tmp_path / f"{'b' * 32}.webp"
    stale.write_bytes(PNG_BYTES)
    os.utime(stale, (time.time() - 61, time.time() - 61))

    assert cleanup_expired_provider_media(tmp_path, ttl_seconds=60, now=time.time()) == 1
    assert not stale.exists()
