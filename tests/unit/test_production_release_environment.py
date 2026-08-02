from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UPDATER = ROOT / "infra" / "prod" / "update_production_release.py"
OLD_SHA = "1" * 40
NEW_SHA = "2" * 40
OTHER_SHA = "3" * 40


def _write_environment(path: Path, release_sha: str = OLD_SHA) -> None:
    path.parent.mkdir(mode=0o700)
    path.write_bytes(
        (f"SHANHAI_RELEASE_SHA={release_sha}\r\nSHANHAI_PUBLIC_IP=203.0.113.10\r\n").encode()
    )
    path.chmod(0o600)


def _run_updater(
    path: Path,
    expected_sha: str = OLD_SHA,
    new_sha: str = NEW_SHA,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(UPDATER),
            str(path),
            expected_sha,
            new_sha,
            str(os.getuid()),
            "600",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _run_inspector(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(UPDATER),
            "inspect",
            str(path),
            str(os.getuid()),
            "600",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="production environment ownership and atomic replacement require Linux",
)


def test_inspector_validates_and_prints_the_exact_release_sha(tmp_path: Path) -> None:
    environment = tmp_path / "shared" / "production.env"
    _write_environment(environment)

    result = _run_inspector(environment)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{OLD_SHA}\n"


def test_updater_atomically_replaces_only_the_exact_release_sha(tmp_path: Path) -> None:
    environment = tmp_path / "shared" / "production.env"
    _write_environment(environment)
    original_inode = environment.stat().st_ino

    result = _run_updater(environment)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "production release environment updated\n"
    assert (
        environment.read_bytes()
        == (f"SHANHAI_RELEASE_SHA={NEW_SHA}\r\nSHANHAI_PUBLIC_IP=203.0.113.10\r\n").encode()
    )
    metadata = environment.stat()
    assert metadata.st_ino != original_inode
    assert stat.S_IMODE(metadata.st_mode) == 0o600
    assert metadata.st_nlink == 1


def test_updater_is_idempotent_when_the_target_sha_is_already_active(tmp_path: Path) -> None:
    environment = tmp_path / "shared" / "production.env"
    _write_environment(environment, NEW_SHA)
    original_inode = environment.stat().st_ino

    result = _run_updater(environment)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "production release environment already current\n"
    assert environment.stat().st_ino == original_inode


@pytest.mark.parametrize(
    ("content", "expected_error"),
    [
        (
            "SHANHAI_PUBLIC_IP=203.0.113.10\n",
            "exactly one release SHA entry",
        ),
        (
            f"SHANHAI_RELEASE_SHA={OLD_SHA}\nSHANHAI_RELEASE_SHA={OLD_SHA}\n",
            "exactly one release SHA entry",
        ),
        (
            f"SHANHAI_RELEASE_SHA={OTHER_SHA}\n",
            "does not match expected SHA",
        ),
    ],
)
def test_updater_rejects_ambiguous_or_stale_state_without_writing(
    tmp_path: Path,
    content: str,
    expected_error: str,
) -> None:
    environment = tmp_path / "shared" / "production.env"
    environment.parent.mkdir(mode=0o700)
    environment.write_text(content, encoding="utf-8")
    environment.chmod(0o600)
    before = environment.read_bytes()
    original_inode = environment.stat().st_ino

    result = _run_updater(environment)

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert environment.read_bytes() == before
    assert environment.stat().st_ino == original_inode


@pytest.mark.parametrize(
    "unsafe_kind",
    ["symlink", "hardlink", "wide-mode", "nonregular", "wrong-identity"],
)
def test_updater_rejects_unsafe_environment_files_without_writing(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    shared = tmp_path / "shared"
    environment = shared / "production.env"
    _write_environment(environment)
    target = environment
    if unsafe_kind == "symlink":
        target = shared / "linked.env"
        target.symlink_to(environment)
    elif unsafe_kind == "hardlink":
        target = shared / "hardlinked.env"
        os.link(environment, target)
    elif unsafe_kind == "wide-mode":
        environment.chmod(0o644)
    elif unsafe_kind == "nonregular":
        target = shared / "named-pipe.env"
        os.mkfifo(target)
    before = environment.read_bytes()

    if unsafe_kind == "wrong-identity":
        result = subprocess.run(
            [
                sys.executable,
                str(UPDATER),
                str(target),
                OLD_SHA,
                NEW_SHA,
                str(os.getuid() + 1),
                "600",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    else:
        result = _run_updater(target)

    assert result.returncode != 0
    assert "unsafe" in result.stderr
    assert environment.read_bytes() == before


@pytest.mark.skipif(
    getattr(os, "geteuid", lambda: 1)() != 0,
    reason="changing the environment file owner requires root",
)
def test_updater_rejects_a_file_owned_by_another_user_without_writing(tmp_path: Path) -> None:
    environment = tmp_path / "shared" / "production.env"
    _write_environment(environment)
    before = environment.read_bytes()
    os.chown(environment, 1, environment.stat().st_gid)

    result = _run_updater(environment)

    assert result.returncode != 0
    assert "file owner is unsafe" in result.stderr
    assert environment.read_bytes() == before


def test_updater_rejects_an_unsafe_parent_directory_without_writing(tmp_path: Path) -> None:
    environment = tmp_path / "shared" / "production.env"
    _write_environment(environment)
    environment.parent.chmod(0o722)
    before = environment.read_bytes()
    original_inode = environment.stat().st_ino

    result = _run_updater(environment)

    assert result.returncode != 0
    assert "directory is unsafe" in result.stderr
    assert environment.read_bytes() == before
    assert environment.stat().st_ino == original_inode


def test_updater_rejects_relative_paths_and_redacts_release_values() -> None:
    result = _run_updater(Path("production.env"), expected_sha=OTHER_SHA)

    assert result.returncode != 0
    assert "path must be absolute" in result.stderr
    assert OLD_SHA not in result.stderr
    assert NEW_SHA not in result.stderr
    assert OTHER_SHA not in result.stderr
