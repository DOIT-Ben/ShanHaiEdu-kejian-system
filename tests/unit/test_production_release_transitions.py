from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROD = ROOT / "infra" / "prod"
CURRENT_SHA = "4" * 40
PREVIOUS_SHA = "5" * 40


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _prepare_rollback_environment(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    production_root = tmp_path / "production"
    shared = production_root / "shared"
    shared.mkdir(parents=True, mode=0o700)
    environment = shared / "production.env"
    environment.write_text(f"SHANHAI_RELEASE_SHA={CURRENT_SHA}\n", encoding="utf-8")
    environment.chmod(0o600)

    current_source = production_root / "releases" / CURRENT_SHA
    previous_source = production_root / "releases" / PREVIOUS_SHA
    for source, release_sha in (
        (current_source, CURRENT_SHA),
        (previous_source, PREVIOUS_SHA),
    ):
        prod = source / "infra" / "prod"
        prod.mkdir(parents=True)
        (source / "RELEASE_SHA").write_text(f"{release_sha}\n", encoding="utf-8")
        (prod / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    _write_executable(previous_source / "infra" / "prod" / "verify.sh", "#!/bin/sh\nexit 0\n")

    (production_root / "current").symlink_to(current_source, target_is_directory=True)
    (production_root / "previous-release").symlink_to(
        previous_source,
        target_is_directory=True,
    )

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    command_log = tmp_path / "commands.log"
    _write_executable(
        fake_bin / "docker",
        '#!/bin/sh\nprintf "docker %s\\n" "$*" >> "$SHANHAI_TEST_COMMAND_LOG"\n',
    )
    _write_executable(
        fake_bin / "nginx",
        "#!/bin/sh\n"
        'printf "nginx %s\\n" "$*" >> "$SHANHAI_TEST_COMMAND_LOG"\n'
        'if [ "${SHANHAI_TEST_FAIL_NGINX:-0}" = "1" ]; then exit 1; fi\n',
    )
    _write_executable(
        fake_bin / "systemctl",
        '#!/bin/sh\nprintf "systemctl %s\\n" "$*" >> "$SHANHAI_TEST_COMMAND_LOG"\n',
    )
    env = {
        "PATH": f"{fake_bin}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "SHANHAI_PRODUCTION_ROOT": str(production_root),
        "SHANHAI_TEST_COMMAND_LOG": str(command_log),
    }
    return production_root, environment, command_log, env


def _resolve_link(path: Path) -> Path:
    return Path(os.path.realpath(path))


def test_release_and_rollback_persist_the_exact_release_under_the_operation_lock() -> None:
    release = (PROD / "release.sh").read_text(encoding="utf-8")
    rollback = (PROD / "rollback.sh").read_text(encoding="utf-8")
    updater = "update_production_release.py"
    release_update = 'update_release_environment "$environment_release_sha" "$release_sha"'
    release_restore = 'update_release_environment "$release_sha" "$environment_release_sha"'
    release_validate = (
        'update_release_environment "$environment_release_sha" "$environment_release_sha"'
    )
    rollback_update = 'update_release_environment "$current_sha" "$previous_sha"'
    rollback_restore = 'update_release_environment "$previous_sha" "$current_sha"'
    rollback_validate = (
        'update_release_environment "$environment_release_sha" "$environment_release_sha"'
    )

    assert updater in release
    assert updater in rollback
    assert (
        'python3 "$source_root/infra/prod/update_production_release.py" '
        '"$environment_file" "$1" "$2" 0 600'
    ) in release
    assert (
        'python3 "$script_root/update_production_release.py" "$environment_file" "$1" "$2" 0 600'
    ) in rollback
    assert 'environment_release_sha="$(' in release
    assert 'sourced_environment_release_sha="${SHANHAI_RELEASE_SHA:?"' in release
    assert release_restore in release
    assert release_update in release
    assert release.index(release_validate) < release.index('source "$environment_file"')
    assert release.index("flock --exclusive --wait 60 9") < release.index(release_update)
    assert release.index('ln -sfn "$source_root" "$production_root/current"') < release.index(
        release_update
    )
    assert release.index(release_restore) < release.index(
        'SHANHAI_RELEASE_SHA="$previous_sha" docker compose'
    )

    assert 'current_source="$(readlink -f "$production_root/current")"' in rollback
    assert 'current_sha="$(tr -d \'\\r\\n\' < "$current_source/RELEASE_SHA")"' in rollback
    assert 'sourced_environment_release_sha="${SHANHAI_RELEASE_SHA:?"' in rollback
    assert "trap rollback_rollback ERR" in rollback
    assert rollback_restore in rollback
    assert rollback_update in rollback
    assert rollback.index(rollback_validate) < rollback.index('source "$environment_file"')
    assert rollback.index("flock --exclusive --wait 60 9") < rollback.index(rollback_update)
    assert rollback.index('ln -sfn "$previous_source" "$production_root/current"') < rollback.index(
        rollback_update
    )
    assert rollback.index(rollback_restore) < rollback.index(
        'SHANHAI_RELEASE_SHA="$current_sha" docker compose'
    )


@pytest.mark.skipif(
    sys.platform == "win32" or getattr(os, "geteuid", lambda: 1)() != 0,
    reason="production rollback behavior requires a root Linux runtime",
)
def test_rollback_atomically_switches_links_and_environment(tmp_path: Path) -> None:
    production_root, environment, command_log, env = _prepare_rollback_environment(tmp_path)

    result = subprocess.run(
        ["bash", str(PROD / "rollback.sh")],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert _resolve_link(production_root / "current").name == PREVIOUS_SHA
    assert _resolve_link(production_root / "previous-release").name == CURRENT_SHA
    assert environment.read_text(encoding="utf-8") == f"SHANHAI_RELEASE_SHA={PREVIOUS_SHA}\n"
    commands = command_log.read_text(encoding="utf-8")
    assert f"-f {production_root}/releases/{PREVIOUS_SHA}/infra/prod/compose.yaml" in commands
    assert "nginx -t" in commands
    assert "systemctl reload nginx" in commands


@pytest.mark.skipif(
    sys.platform == "win32" or getattr(os, "geteuid", lambda: 1)() != 0,
    reason="production rollback behavior requires a root Linux runtime",
)
def test_rollback_failure_restores_links_environment_and_current_application(
    tmp_path: Path,
) -> None:
    production_root, environment, command_log, env = _prepare_rollback_environment(tmp_path)
    env["SHANHAI_TEST_FAIL_NGINX"] = "1"

    result = subprocess.run(
        ["bash", str(PROD / "rollback.sh")],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert "application restoration was attempted" in result.stderr
    assert _resolve_link(production_root / "current").name == CURRENT_SHA
    assert _resolve_link(production_root / "previous-release").name == PREVIOUS_SHA
    assert environment.read_text(encoding="utf-8") == f"SHANHAI_RELEASE_SHA={CURRENT_SHA}\n"
    commands = command_log.read_text(encoding="utf-8")
    assert f"-f {production_root}/releases/{PREVIOUS_SHA}/infra/prod/compose.yaml" in commands
    assert f"-f {production_root}/releases/{CURRENT_SHA}/infra/prod/compose.yaml" in commands
