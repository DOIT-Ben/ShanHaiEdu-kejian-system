from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "infra" / "prod"
RELEASE_SHA = "a" * 40
API_IMAGE_ID = f"sha256:{'1' * 64}"
WEB_IMAGE_ID = f"sha256:{'2' * 64}"
ARCHIVE_SHA256 = "3" * 64
WINDOWS_GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
BASH = (
    str(WINDOWS_GIT_BASH)
    if os.name == "nt" and WINDOWS_GIT_BASH.exists()
    else shutil.which("bash") or "bash"
)


def _shell_path(path: Path) -> str:
    resolved = path.resolve()
    if os.name != "nt":
        return resolved.as_posix()
    drive = resolved.drive.rstrip(":").lower()
    tail = "/".join(resolved.parts[1:])
    return f"/{drive}/{tail}"


def _write_fake_docker(fake_bin: Path) -> None:
    docker = fake_bin / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
set -eu
[[ "${1:-}" == "image" && "${2:-}" == "inspect" ]] || exit 90
image="${3:-}"
format="${5:-}"
if [[ "${FAKE_DOCKER_MISSING_IMAGE:-}" == "$image" ]]; then
  exit 1
fi
if [[ "$image" == shanhaiedu-api:* ]]; then
  image_id="${FAKE_API_IMAGE_ID-}"
  revision="${FAKE_API_REVISION-}"
elif [[ "$image" == shanhaiedu-web:* ]]; then
  image_id="${FAKE_WEB_IMAGE_ID-}"
  revision="${FAKE_WEB_REVISION-}"
else
  exit 1
fi
if [[ "$format" == "{{.Id}}" ]]; then
  printf '%s\\n' "$image_id"
elif [[ "$format" == *org.opencontainers.image.revision* ]]; then
  printf '%s\\n' "$revision"
else
  exit 91
fi
""",
        encoding="utf-8",
        newline="\n",
    )
    docker.chmod(0o755)


def _write_preloaded_manifest(
    production_root: Path,
    *,
    api_image_id: str = API_IMAGE_ID,
    archive_sha256: str = ARCHIVE_SHA256,
) -> Path:
    manifest = production_root / "shared" / "preloaded-images" / f"{RELEASE_SHA}.env"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        f"SHANHAI_RELEASE_SHA={RELEASE_SHA}\n"
        f"SHANHAI_PRELOADED_API_IMAGE_ID={api_image_id}\n"
        f"SHANHAI_PRELOADED_WEB_IMAGE_ID={WEB_IMAGE_ID}\n"
        f"SHANHAI_PRELOADED_ARCHIVE_SHA256={archive_sha256}\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest.chmod(0o600)
    return manifest


def _manifest_stat(manifest: Path) -> tuple[str, str]:
    result = subprocess.run(
        [
            BASH,
            "-c",
            'stat -c "%u %a" "$1"',
            "shanhai-manifest-stat",
            _shell_path(manifest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    owner, mode = result.stdout.strip().split()
    return owner, mode


def _run_image_source_preflight(
    production_root: Path,
    fake_bin: Path,
    *,
    image_source: str | None,
    environment: dict[str, str] | None = None,
    expected_manifest_mode: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if image_source is None:
        env.pop("SHANHAI_IMAGE_SOURCE", None)
    else:
        env["SHANHAI_IMAGE_SOURCE"] = image_source
    env.update(
        {
            "PATH": f"{_shell_path(fake_bin)}:{env['PATH']}",
            "FAKE_API_IMAGE_ID": API_IMAGE_ID,
            "FAKE_WEB_IMAGE_ID": WEB_IMAGE_ID,
            "FAKE_API_REVISION": RELEASE_SHA,
            "FAKE_WEB_REVISION": RELEASE_SHA,
        }
    )
    if environment:
        env.update(environment)

    manifest = production_root / "shared" / "preloaded-images" / f"{RELEASE_SHA}.env"
    if manifest.exists():
        expected_owner, expected_mode = _manifest_stat(manifest)
        expected_mode = expected_manifest_mode or expected_mode
    else:
        expected_owner, expected_mode = "0", "600"

    return subprocess.run(
        [
            BASH,
            _shell_path(PROD / "validate-image-source.sh"),
            RELEASE_SHA,
            _shell_path(production_root),
            expected_owner,
            expected_mode,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_image_source_preflight_defaults_to_build_without_writes(tmp_path: Path) -> None:
    production_root = tmp_path / "production"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin)

    result = _run_image_source_preflight(production_root, fake_bin, image_source=None)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "build"
    assert not production_root.exists()


def test_image_source_preflight_rejects_invalid_mode_without_writes(
    tmp_path: Path,
) -> None:
    production_root = tmp_path / "production"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin)

    result = _run_image_source_preflight(production_root, fake_bin, image_source="invalid")

    assert result.returncode != 0
    assert "must be build or preloaded" in result.stderr
    assert not production_root.exists()


def test_image_source_preflight_accepts_exact_preloaded_manifest(
    tmp_path: Path,
) -> None:
    production_root = tmp_path / "production"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin)
    _write_preloaded_manifest(production_root)

    result = _run_image_source_preflight(production_root, fake_bin, image_source="preloaded")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "preloaded"


def test_image_source_preflight_rejects_manifest_with_wrong_mode_without_writes(
    tmp_path: Path,
) -> None:
    production_root = tmp_path / "production"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin)
    _write_preloaded_manifest(production_root)
    before = sorted(path.relative_to(production_root) for path in production_root.rglob("*"))

    result = _run_image_source_preflight(
        production_root,
        fake_bin,
        image_source="preloaded",
        expected_manifest_mode="777",
    )

    after = sorted(path.relative_to(production_root) for path in production_root.rglob("*"))
    assert result.returncode != 0
    assert "manifest ownership or mode is invalid" in result.stderr
    assert after == before


@pytest.mark.parametrize(
    ("api_image_id", "archive_sha256", "error"),
    [
        ("", ARCHIVE_SHA256, "manifest image ID is invalid"),
        (API_IMAGE_ID, "invalid", "manifest archive SHA-256 is invalid"),
    ],
)
def test_image_source_preflight_rejects_incomplete_manifest_without_writes(
    tmp_path: Path, api_image_id: str, archive_sha256: str, error: str
) -> None:
    production_root = tmp_path / "production"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin)
    _write_preloaded_manifest(
        production_root,
        api_image_id=api_image_id,
        archive_sha256=archive_sha256,
    )
    before = sorted(path.relative_to(production_root) for path in production_root.rglob("*"))

    result = _run_image_source_preflight(production_root, fake_bin, image_source="preloaded")

    after = sorted(path.relative_to(production_root) for path in production_root.rglob("*"))
    assert result.returncode != 0
    assert error in result.stderr
    assert after == before


@pytest.mark.parametrize(
    ("environment", "error"),
    [
        (
            {"FAKE_DOCKER_MISSING_IMAGE": f"shanhaiedu-api:{RELEASE_SHA}"},
            "image is unavailable",
        ),
        ({"FAKE_API_IMAGE_ID": ""}, "image ID is invalid"),
        ({"FAKE_API_IMAGE_ID": f"sha256:{'4' * 64}"}, "image ID does not match"),
        ({"FAKE_API_REVISION": ""}, "revision is missing"),
        ({"FAKE_API_REVISION": "b" * 40}, "revision does not match"),
    ],
)
def test_image_source_preflight_rejects_untrusted_preloaded_images_without_writes(
    tmp_path: Path, environment: dict[str, str], error: str
) -> None:
    production_root = tmp_path / "production"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_docker(fake_bin)
    _write_preloaded_manifest(production_root)
    before = sorted(path.relative_to(production_root) for path in production_root.rglob("*"))

    result = _run_image_source_preflight(
        production_root,
        fake_bin,
        image_source="preloaded",
        environment=environment,
    )

    after = sorted(path.relative_to(production_root) for path in production_root.rglob("*"))
    assert result.returncode != 0
    assert error in result.stderr
    assert after == before
