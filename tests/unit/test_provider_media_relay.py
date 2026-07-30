from __future__ import annotations

import base64
import hashlib
import json
import os
import re
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


def test_standalone_cleanup_rejects_ttl_above_runtime_limit(tmp_path: Path) -> None:
    stale = tmp_path / f"{'c' * 32}.jpg"
    stale.write_bytes(PNG_BYTES)
    os.utime(stale, (time.time() - 3_602, time.time() - 3_602))
    script = Path(__file__).resolve().parents[2] / "apps/api/provider_media_relay.py"
    environment = os.environ.copy()
    environment["SHANHAI_PROVIDER_MEDIA_ROOT"] = str(tmp_path)
    environment["SHANHAI_PROVIDER_MEDIA_MAX_TTL_SECONDS"] = "3601"
    environment.pop("SHANHAI_PROVIDER_MEDIA_SIGNING_SECRET", None)

    completed = subprocess.run(
        [sys.executable, "-I", str(script), "--cleanup"],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    assert completed.returncode != 0
    assert "between 1 and 3600" in completed.stderr
    assert stale.exists()


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
    assert 'sudo -u shanhai-dev -H git -C "${repository_root}" rev-parse origin/main' in runbook
    assert 'sha256sum "${relay_staging}"' in runbook
    assert "sha256sum /opt/shanhaiedu/provider-media-relay/provider_media_relay.py" in runbook
    assert "date -u +%Y-%m-%dT%H:%M:%SZ" in runbook


def test_relay_deploy_provenance_fails_closed_before_mutation() -> None:
    root = Path(__file__).resolve().parents[2]
    runbook = (root / "infra/provider-media-relay/README.md").read_text(encoding="utf-8")
    fetch = 'sudo -u shanhai-dev -H git -C "${repository_root}" fetch origin --prune'
    staged_blob = (
        'sudo -u shanhai-dev -H git -C "${repository_root}" show '
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
    preflight_url = 'old_url_preflight="$(printf \'%s\' "${old_secret}"'
    first_mutation = runbook.index('backup_root="$(mktemp -d')
    assert runbook.index(preflight_url) < runbook.index("curl --fail") < first_mutation
    assert 'test "${old_secret}" != "${new_secret}"' in runbook
    assert 'old_url="$(printf \'%s\' "${old_secret}"' in runbook
    assert runbook.count("PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -c") == 3
    assert "passwd -S shanhai-relay" in runbook
    assert "/usr/sbin/nologin" in runbook
    assert "UID_MIN" in runbook
    assert "provider-media-cleanup-keep.txt" in runbook
    assert "journalctl -u shanhai-provider-media-relay.service" in runbook
    rollback = runbook.split("## Rollback", 1)[1]
    backup_pointer = "/srv/shanhaiedu/backups/provider-media-relay-prechange.current"
    pointer_write = 'printf \'%s\\n\' "${backup_root}" > "${backup_pointer}"'
    assert f"backup_pointer={backup_pointer}" in runbook
    assert 'test ! -e "${backup_pointer}"' in runbook
    assert runbook.index(pointer_write) < runbook.index("id -u shanhai-relay")
    assert 'IFS= read -r backup_root < "${backup_pointer}"' in rollback
    assert (
        "read -r relay_was_active relay_was_enabled timer_was_active timer_was_enabled" in rollback
    )
    assert 'if systemctl cat "${unit}"' in rollback
    assert "relay_was_active" in rollback
    assert "relay_was_enabled" in rollback
    assert "provider_media_relay.py" in rollback
    assert "shanhai-provider-media-relay.conf" in rollback
    assert "systemctl restart shanhai-provider-media-relay.service" in rollback


def test_relay_deploy_post_start_gates_report_only_redacted_phase_and_line() -> None:
    root = Path(__file__).resolve().parents[2]
    runbook = (root / "infra/provider-media-relay/README.md").read_text(encoding="utf-8")
    deploy = runbook.split("## Deploy", 1)[1].split("## HTTPS Smoke", 1)[0]

    assert 'trap \'relay_deploy_error "${LINENO}" "$?"\' ERR' in deploy
    assert "relay-deploy-failed phase=%s line=%s status=%s\\n" in deploy
    assert "BASH_COMMAND" not in deploy
    assert "set -x" not in deploy
    assert "set -o xtrace" not in deploy
    assert "bash -x" not in deploy
    assert deploy.index("set +x") < deploy.index("producer_env=")

    post_start_gates = {
        "cleanup-oneshot-result": (
            'test "$(systemctl show provider-media-cleanup.service -p Result --value)" = "success"'
        ),
        "cleanup-oneshot-status": (
            'test "$(systemctl show provider-media-cleanup.service -p ExecMainStatus --value)" '
            '= "0"'
        ),
        "relay-active": "systemctl is-active --quiet shanhai-provider-media-relay.service",
        "cleanup-timer-active": "systemctl is-active --quiet provider-media-cleanup.timer",
        "relay-user": (
            'test "$(systemctl show shanhai-provider-media-relay.service -p User --value)" '
            '= "shanhai-relay"'
        ),
        "relay-exec-start": (
            "systemctl show shanhai-provider-media-relay.service -p ExecStart --value | "
            "grep -Fq '/opt/shanhaiedu/provider-media-relay/provider_media_relay.py'"
        ),
        "relay-pid-owner": (
            'test "${relay_pid}" -gt 1\n'
            '   test "$(stat -c \'%U\' "/proc/${relay_pid}")" = "shanhai-relay"'
        ),
        "producer-process-isolation": (
            'if sudo -u shanhai-dev -- cat "/proc/${relay_pid}/environ" '
            ">/dev/null 2>&1; then false; fi"
        ),
        "nginx-config": "nginx -t",
        "nginx-reload": "systemctl reload nginx",
    }
    previous_gate = deploy.index("systemctl restart shanhai-provider-media-relay.service")
    for phase, command in post_start_gates.items():
        marker = f"relay_deploy_phase={phase}"
        marker_index = deploy.index(marker, previous_gate)
        command_index = deploy.index(command, marker_index)
        assert marker_index < command_index
        previous_gate = command_index

    bootstrap = deploy.split("```bash", 1)[1].split("repository_root=", 1)[0]
    completed = subprocess.run(
        ["bash", "-s"],
        input=(bootstrap + "relay_deploy_phase=relay-user\nfalse\n").encode("utf-8"),
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 1
    assert completed.stdout == b""
    assert re.fullmatch(
        r"relay-deploy-failed phase=relay-user line=\d+ status=1\n?",
        completed.stderr.decode("utf-8"),
    )

    sentinel = "do-not-trace-this-fake-secret"
    traced = subprocess.run(
        ["bash", "-x", "-s"],
        input=(
            bootstrap
            + "relay_deploy_phase=xtrace-disabled\n"
            + f"fake_secret={sentinel}\n"
            + "false\n"
        ).encode("utf-8"),
        check=False,
        capture_output=True,
    )
    assert traced.returncode == 1
    assert sentinel.encode("utf-8") not in traced.stderr


def test_relay_deploy_smokes_keep_exact_phase_diagnostics() -> None:
    root = Path(__file__).resolve().parents[2]
    runbook = (root / "infra/provider-media-relay/README.md").read_text(encoding="utf-8")
    post_start = runbook.split("## HTTPS Smoke", 1)[1].split("## Rollback", 1)[0]
    gates = {
        "https-smoke-file": 'test -f "${smoke_path}"',
        "https-smoke-permissions": (
            'test "$(stat -c \'%U:%G:%a\' "${smoke_path}")" = "shanhai-dev:shanhai-dev:640"'
        ),
        "https-new-url-sign": 'url="$(cd /opt/shanhaiedu/provider-media-relay',
        "https-old-url-sign": 'old_url="$(printf \'%s\' "${old_secret}"',
        "https-new-url-fetch": 'curl --fail --silent --show-error --output /dev/null "$url"',
        "https-tampered-url-rejected": (
            'tampered_status="$(curl --silent --show-error --output /dev/null '
            '--write-out \'%{http_code}\' "${url}x")"\n'
            'test "${tampered_status}" = "404"'
        ),
        "https-old-url-rejected": (
            'old_url_status="$(curl --silent --show-error --output /dev/null '
            '--write-out \'%{http_code}\' "${old_url}")"\n'
            'test "${old_url_status}" = "404"'
        ),
        "https-smoke-remove": 'rm -f -- "${smoke_path}"',
        "cleanup-opaque-absent": 'test ! -e "${opaque_smoke}"',
        "cleanup-partial-absent": 'test ! -e "${partial_smoke}"',
        "cleanup-keep-absent": 'test ! -e "${keep_smoke}"',
        "cleanup-timer-wait": "for _attempt in $(seq 1 90); do",
        "cleanup-opaque-removed": 'test ! -e "${opaque_smoke}"',
        "cleanup-partial-removed": 'test ! -e "${partial_smoke}"',
        "cleanup-unrelated-preserved": 'test -f "${keep_smoke}"',
        "cleanup-marker-remove": 'rm -f -- "${keep_smoke}"',
        "cleanup-oneshot-final-result": (
            'test "$(systemctl show provider-media-cleanup.service -p Result --value)" = "success"'
        ),
        "relay-log-read": (
            'relay_journal="$(journalctl -u shanhai-provider-media-relay.service '
            "--since '-10 minutes' --no-pager)\""
        ),
        "relay-log-redaction": (
            "relay_log_status=0\n"
            "grep -Fq 'signature=' <<< \"${relay_journal}\" || relay_log_status=$?\n"
            'test "${relay_log_status}" -eq 1'
        ),
        "nginx-log-redaction": (
            "nginx_log_status=0\n"
            "grep -Fq 'signature=' /var/log/nginx/access.log 2>/dev/null || "
            "nginx_log_status=$?\n"
            'test "${nginx_log_status}" -eq 1'
        ),
    }
    previous_gate = 0
    for phase, command in gates.items():
        marker_index = post_start.index(f"relay_deploy_phase={phase}", previous_gate)
        command_index = post_start.index(command, marker_index)
        assert marker_index < command_index
        previous_gate = command_index

    assert "then exit 1" not in post_start
    assert (
        'test ! -e "${opaque_smoke}" && test ! -e "${partial_smoke}" && test ! -e "${keep_smoke}"'
    ) not in post_start

    deploy = runbook.split("## Deploy", 1)[1].split("## HTTPS Smoke", 1)[0]
    bootstrap = deploy.split("```bash", 1)[1].split("repository_root=", 1)[0]
    injected = ""
    for phase in gates:
        injected += (
            "(\n"
            + bootstrap
            + f"relay_deploy_phase={phase}\n"
            + "false\n"
            + ")\n"
            + "test $? -eq 1 || exit 90\n"
        )
    completed = subprocess.run(
        ["bash", "-s"],
        input=injected.encode("utf-8"),
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0
    assert completed.stdout == b""
    reported_phases = []
    for line in completed.stderr.decode("utf-8").splitlines():
        match = re.fullmatch(
            r"relay-deploy-failed phase=([a-z0-9-]+) line=\d+ status=1",
            line,
        )
        assert match is not None, line
        reported_phases.append(match.group(1))
    assert reported_phases == list(gates)

    tampered_gate = (
        "relay_deploy_phase=https-tampered-url-rejected\n"
        + post_start.split("relay_deploy_phase=https-tampered-url-rejected\n", 1)[1].split(
            "relay_deploy_phase=https-old-url-rejected", 1
        )[0]
    )
    for fake_curl, expected_status in (
        ("curl() { printf '404'; return 0; }\n", 0),
        ("curl() { printf '500'; return 0; }\n", 1),
        ("curl() { return 7; }\n", 7),
    ):
        completed = subprocess.run(
            ["bash", "-s"],
            input=(bootstrap + fake_curl + "url=https://invalid.example\n" + tampered_gate).encode(
                "utf-8"
            ),
            check=False,
            capture_output=True,
        )
        assert completed.returncode == expected_status

    relay_log_gate = (
        "relay_deploy_phase=relay-log-read\n"
        + post_start.split("relay_deploy_phase=relay-log-read\n", 1)[1].split(
            "relay_deploy_phase=nginx-log-redaction", 1
        )[0]
    )
    for fake_journal, expected_status, forbidden in (
        ("journalctl() { printf 'safe log'; return 0; }\n", 0, b""),
        ("journalctl() { return 1; }\n", 1, b""),
        ("journalctl() { printf 'signature=fake-secret'; return 0; }\n", 1, b"fake-secret"),
    ):
        completed = subprocess.run(
            ["bash", "-s"],
            input=(bootstrap + fake_journal + relay_log_gate).encode("utf-8"),
            check=False,
            capture_output=True,
        )
        assert completed.returncode == expected_status
        if forbidden:
            assert forbidden not in completed.stderr

    nginx_log_gate = (
        "relay_deploy_phase=nginx-log-redaction\n"
        + post_start.split("relay_deploy_phase=nginx-log-redaction\n", 1)[1].split(
            "relay_deploy_phase=migration-complete", 1
        )[0]
    )
    for grep_status, expected_status in ((1, 0), (0, 1), (2, 1)):
        completed = subprocess.run(
            ["bash", "-s"],
            input=(bootstrap + f"grep() {{ return {grep_status}; }}\n" + nginx_log_gate).encode(
                "utf-8"
            ),
            check=False,
            capture_output=True,
        )
        assert completed.returncode == expected_status


def test_relay_runbook_pre_rollback_blocks_are_lf_safe_base64_bash() -> None:
    root = Path(__file__).resolve().parents[2]
    raw_runbook = (root / "infra/provider-media-relay/README.md").read_bytes()
    attributes = (root / ".gitattributes").read_text(encoding="utf-8")
    assert "/infra/provider-media-relay/README.md text eol=lf" in attributes
    assert b'[Text.Encoding]::UTF8.GetBytes(($relayScriptText -replace "`r`n?", "`n"))' in (
        raw_runbook
    )
    assert b"[Convert]::ToBase64String($relayScriptBytes)" in raw_runbook
    normalized = raw_runbook.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    pre_rollback = normalized.split(b"## Rollback", 1)[0]
    blocks = re.findall(rb"^[ ]*```bash\n(.*?)^[ ]*```", pre_rollback, re.MULTILINE | re.DOTALL)
    assert len(blocks) == 9
    script = b"\n".join(re.sub(rb"(?m)^   ", b"", block) for block in blocks)
    payload = base64.b64encode(script)
    transported = base64.b64decode(payload, validate=True)

    assert b"\r" not in transported
    completed = subprocess.run(
        ["bash", "-n"],
        input=transported,
        check=False,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8")


def test_cleanup_contract_is_shared_by_runtime_and_model_gateway(tmp_path: Path) -> None:
    stale = tmp_path / f"{'b' * 32}.webp"
    stale.write_bytes(PNG_BYTES)
    os.utime(stale, (time.time() - 61, time.time() - 61))

    assert cleanup_expired_provider_media(tmp_path, ttl_seconds=60, now=time.time()) == 1
    assert not stale.exists()
