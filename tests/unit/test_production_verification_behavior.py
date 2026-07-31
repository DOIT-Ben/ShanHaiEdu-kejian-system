from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "infra" / "prod" / "verify.sh"
RELEASE_SHA = "793bd6d7127d91610cccb1b1afc81003a63b6523"
STALE_RELEASE_SHA = "0f6a8477ce0d17496e6f5eeb71a81a6bd9d330be"


def _write_executable(path: Path, content: str) -> None:
    path.write_bytes(content.encode("utf-8"))
    path.chmod(0o755)


def _bash_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name != "nt":
        return resolved.as_posix()
    drive = resolved.drive.rstrip(":").lower()
    return f"/{drive}/{resolved.as_posix()[3:]}"


def _find_bash() -> str:
    bash = shutil.which("bash")
    if os.name == "nt":
        git = shutil.which("git")
        assert git is not None
        git_bash = Path(git).resolve().parents[1] / "bin" / "bash.exe"
        if git_bash.is_file():
            bash = str(git_bash)
    assert bash is not None
    return bash


def _run_verification(
    tmp_path: Path,
    mode: str,
    *,
    docker_logs: str = "",
    environment_release_sha: str = RELEASE_SHA,
    explicit_release_sha: str | None = None,
    expected_release_sha: str = RELEASE_SHA,
) -> tuple[subprocess.CompletedProcess[str], list[str], int, int]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    curl_count = tmp_path / "curl-count"
    curl_calls = tmp_path / "curl-calls"
    sleep_count = tmp_path / "sleep-count"
    environment_file = tmp_path / "production.env"
    curl_count.write_text("0", encoding="utf-8")
    curl_calls.write_text("", encoding="utf-8")
    sleep_count.write_text("0", encoding="utf-8")
    environment_file.write_text(
        f"SHANHAI_RELEASE_SHA={environment_release_sha}\n",
        encoding="utf-8",
    )

    _write_executable(
        fake_bin / "curl",
        """#!/usr/bin/env bash
set -eu
count="$(( $(cat "$FAKE_CURL_COUNT") + 1 ))"
printf '%s' "$count" > "$FAKE_CURL_COUNT"
url="${@: -1}"
printf '%s\n' "$url" >> "$FAKE_CURL_CALLS"
case "$FAKE_CURL_MODE" in
  unavailable) exit 7 ;;
  recover) [[ "$count" -eq 1 ]] && exit 7 ;;
  wrong-release)
    printf '%s' '{"data":{"release_sha":"wrong"}}'
    exit 0
    ;;
  invalid-json)
    printf '%s' 'not-json'
    exit 0
    ;;
esac
if [[ "$url" == */health/live ]]; then
  printf '{"data":{"release_sha":"%s"}}' "$EXPECTED_RELEASE_SHA"
else
  printf '%s' ok
fi
""",
    )
    _write_executable(
        fake_bin / "sleep",
        """#!/usr/bin/env bash
set -eu
count="$(( $(cat "$FAKE_SLEEP_COUNT") + 1 ))"
printf '%s' "$count" > "$FAKE_SLEEP_COUNT"
""",
    )
    _write_executable(
        fake_bin / "docker",
        """#!/usr/bin/env bash
set -eu
case "$*" in
  *"logs --since 10m"*) printf '%s' "${FAKE_DOCKER_LOGS:-}" ;;
  *"redis redis-cli ping"*) printf '%s\n' PONG ;;
  *"postgres pg_isready"*) printf '%s\n' accepting ;;
esac
""",
    )
    _write_executable(
        fake_bin / "python3",
        f'#!/usr/bin/env bash\nexec "{_bash_path(Path(sys.executable))}" "$@"\n',
    )

    env = os.environ.copy()
    env.pop("SHANHAI_RELEASE_SHA", None)
    env.update(
        {
            "EXPECTED_RELEASE_SHA": expected_release_sha,
            "FAKE_CURL_CALLS": _bash_path(curl_calls),
            "FAKE_CURL_COUNT": _bash_path(curl_count),
            "FAKE_CURL_MODE": mode,
            "FAKE_DOCKER_LOGS": docker_logs,
            "FAKE_SLEEP_COUNT": _bash_path(sleep_count),
            "SHANHAI_ENV_FILE": _bash_path(environment_file),
        }
    )
    if explicit_release_sha is not None:
        env["SHANHAI_RELEASE_SHA"] = explicit_release_sha
    result = subprocess.run(
        [
            _find_bash(),
            "-c",
            'export PATH="$1:$PATH"; "$2" --local',
            "verify-harness",
            _bash_path(fake_bin),
            _bash_path(VERIFY),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    calls = curl_calls.read_text(encoding="utf-8").splitlines()
    return (
        result,
        calls,
        int(curl_count.read_text(encoding="utf-8")),
        int(sleep_count.read_text(encoding="utf-8")),
    )


def test_retries_then_checks_every_loopback_endpoint(tmp_path: Path) -> None:
    result, calls, curl_count, sleep_count = _run_verification(tmp_path, "recover")

    assert result.returncode == 0, result.stderr
    assert calls == [
        "http://127.0.0.1:18080/health/live",
        "http://127.0.0.1:18080/health/live",
        "http://127.0.0.1:18080/health/ready",
        "http://127.0.0.1:18080/",
    ]
    assert curl_count == 4
    assert sleep_count == 1


def test_explicit_release_sha_overrides_stale_environment_file(
    tmp_path: Path,
) -> None:
    result, calls, _, _ = _run_verification(
        tmp_path,
        "available",
        environment_release_sha=STALE_RELEASE_SHA,
        explicit_release_sha=RELEASE_SHA,
        expected_release_sha=RELEASE_SHA,
    )

    assert result.returncode == 0, result.stderr
    assert f"production verification passed: {RELEASE_SHA}" in result.stdout
    assert calls[0] == "http://127.0.0.1:18080/health/live"


def test_environment_file_release_sha_is_fallback_without_explicit_value(
    tmp_path: Path,
) -> None:
    result, _, _, _ = _run_verification(
        tmp_path,
        "available",
        environment_release_sha=STALE_RELEASE_SHA,
        expected_release_sha=STALE_RELEASE_SHA,
    )

    assert result.returncode == 0, result.stderr
    assert f"production verification passed: {STALE_RELEASE_SHA}" in result.stdout


def test_fails_after_bounded_loopback_retries(tmp_path: Path) -> None:
    result, calls, curl_count, sleep_count = _run_verification(tmp_path, "unavailable")

    assert result.returncode != 0
    assert calls == ["http://127.0.0.1:18080/health/live"] * 30
    assert curl_count == 30
    assert sleep_count == 29


@pytest.mark.parametrize("mode", ["wrong-release", "invalid-json"])
def test_rejects_invalid_release_payload(tmp_path: Path, mode: str) -> None:
    result, calls, curl_count, sleep_count = _run_verification(tmp_path, mode)

    assert result.returncode != 0
    assert calls == ["http://127.0.0.1:18080/health/live"]
    assert curl_count == 1
    assert sleep_count == 0


@pytest.mark.parametrize(
    "marker",
    ["X-Amz-Credential=redacted", "X-Amz-Signature=redacted"],
)
def test_rejects_presigned_credential_markers_in_compose_logs(
    tmp_path: Path,
    marker: str,
) -> None:
    result, _, _, _ = _run_verification(tmp_path, "available", docker_logs=marker)

    assert result.returncode != 0
    assert "production logs contain a forbidden secret identifier" in result.stderr
