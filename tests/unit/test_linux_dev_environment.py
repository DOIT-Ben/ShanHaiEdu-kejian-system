from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts.check_linux_dev_environment import (
    validate_versions,
    verify_filesystem,
    verify_workspace_write,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run(
    command: list[str], cwd: Path, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def init_repository(path: Path) -> None:
    path.mkdir()
    assert run(["git", "init", "--quiet"], path).returncode == 0
    (path / "README.md").write_text("test\n", encoding="utf-8")
    assert run(["git", "add", "README.md"], path).returncode == 0
    result = run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "init",
        ],
        path,
    )
    assert result.returncode == 0, result.stderr


def fake_docker_environment(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "info" ]]; then
  printf '%s\\n' '["name=rootless"]'
  exit 0
fi
{
  printf 'args='
  printf '%s ' "$@"
  printf '\\n'
  env | grep '^SHANHAI_' | sort
} > "$FAKE_DOCKER_OUTPUT"
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    disk_free = fake_bin / "df"
    disk_free.write_text(
        """#!/usr/bin/env bash
printf '%s\\n' 'Filesystem 1024-blocks Used Available Capacity Mounted on'
printf '%s\\n' 'fake 100000000 1 99999999 1% /'
""",
        encoding="utf-8",
    )
    disk_free.chmod(0o755)

    env = {key: value for key, value in os.environ.items() if not key.startswith("SHANHAI_")}
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["SHANHAI_DOCKER_ISOLATION_MODE"] = "rootless"
    return fake_bin, env


def run_compose_script(repository: Path, output: Path, env: dict[str, str]) -> dict[str, str]:
    command_env = env | {"FAKE_DOCKER_OUTPUT": str(output)}
    result = run(
        ["bash", str(PROJECT_ROOT / "infra/dev/compose.sh"), "up", "-d"],
        repository,
        env=command_env,
    )
    assert result.returncode == 0, result.stderr
    values = {}
    for line in output.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", maxsplit=1)
        values[key] = value
    return values


def valid_versions() -> dict[str, str]:
    return {
        "python": "Python 3.12.12",
        "uv": "uv 0.10.6 (test)",
        "node": "v22.22.0",
        "pnpm": "10.30.2",
        "git": "git version 2.39.5",
        "ffmpeg": "ffmpeg version 5.1.7",
        "libreoffice": "LibreOffice 7.4.7.2",
    }


def test_pinned_linux_tool_versions_accept_expected_runtime() -> None:
    assert validate_versions(valid_versions()) == []


def test_pinned_linux_tool_versions_reject_runtime_drift() -> None:
    versions = valid_versions()
    versions["node"] = "v20.19.0"
    versions["pnpm"] = "9.15.0"

    assert validate_versions(versions) == [
        "node: expected prefix 'v22.22.0', got 'v20.19.0'",
        "pnpm: expected prefix '10.30.2', got '9.15.0'",
    ]


def test_bootstrap_sync_uses_pinned_system_python() -> None:
    project_root = Path(__file__).resolve().parents[2]
    bootstrap = (project_root / "infra/dev/bootstrap.sh").read_text(encoding="utf-8")

    assert "uv sync --frozen --python /usr/local/bin/python" in bootstrap
    assert "git config --global --replace-all safe.directory /workspace" in bootstrap
    assert "git config --global core.autocrlf input" in bootstrap


def test_verify_checks_staged_and_unstaged_diffs() -> None:
    project_root = Path(__file__).resolve().parents[2]
    verify = (project_root / "infra/dev/verify.sh").read_text(encoding="utf-8")

    assert "git diff --check" in verify
    assert "git diff --cached --check" in verify


def test_compose_shares_only_download_caches_across_worktrees() -> None:
    project_root = Path(__file__).resolve().parents[2]
    compose = yaml.safe_load((project_root / "infra/dev.compose.yaml").read_text(encoding="utf-8"))
    runtime_compose = yaml.safe_load(
        (project_root / "infra/compose.yaml").read_text(encoding="utf-8")
    )

    assert compose["volumes"]["python_venv"] is None
    assert compose["volumes"]["node_modules"] is None
    assert compose["volumes"]["uv_cache"]["name"] == "shanhaiedu-dev-uv-cache-v1"
    assert compose["volumes"]["pnpm_store"]["name"] == "shanhaiedu-dev-pnpm-store-v1"
    assert all(volume is None for volume in runtime_compose["volumes"].values())


def test_compose_mounts_worktree_git_metadata_read_only() -> None:
    project_root = Path(__file__).resolve().parents[2]
    compose = yaml.safe_load((project_root / "infra/dev.compose.yaml").read_text(encoding="utf-8"))
    workspace = compose["services"]["workspace"]
    git_mount = next(
        volume
        for volume in workspace["volumes"]
        if isinstance(volume, dict) and volume.get("target") == "/git-common"
    )

    assert git_mount == {
        "type": "bind",
        "source": "${SHANHAI_GIT_COMMON_DIR:-../.git}",
        "target": "/git-common",
        "read_only": True,
    }
    assert workspace["environment"]["SHANHAI_CONTAINER_GIT_DIR"] == (
        "${SHANHAI_CONTAINER_GIT_DIR:-/git-common}"
    )
    assert workspace["environment"]["SHANHAI_CONTAINER_GIT_WORK_TREE"] == "/workspace"
    assert "GIT_DIR" not in workspace["environment"]
    assert "GIT_WORK_TREE" not in workspace["environment"]


def test_compose_uses_versioned_workspace_image() -> None:
    project_root = Path(__file__).resolve().parents[2]
    compose = yaml.safe_load((project_root / "infra/dev.compose.yaml").read_text(encoding="utf-8"))

    expected = "${SHANHAI_DEV_WORKSPACE_IMAGE:-shanhaiedu-dev-workspace:2026.07-v1}"
    assert compose["services"]["workspace-init"]["image"] == expected
    assert compose["services"]["workspace"]["image"] == expected
    environment = compose["services"]["workspace"]["environment"]
    assert environment["UV_NO_MANAGED_PYTHON"] == "1"
    assert environment["SHANHAI_CONTAINER_ROOTLESS_USERNS"] == (
        "${SHANHAI_CONTAINER_ROOTLESS_USERNS:-false}"
    )
    assert "UV_PYTHON" not in environment


def test_workspace_image_exposes_pnpm_through_dedicated_corepack_shim() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dockerfile = (project_root / "infra/dev/Dockerfile").read_text(encoding="utf-8")

    assert "corepack enable pnpm --install-directory /opt/corepack" in dockerfile
    assert "PATH=/workspace/.venv/bin:/opt/corepack:" in dockerfile


@pytest.mark.skipif(os.name != "posix", reason="Compose host routing is verified on Linux")
def test_compose_script_maps_main_and_linked_worktrees_with_unique_ports(tmp_path: Path) -> None:
    repository = tmp_path / "main-repo"
    init_repository(repository)
    linked = tmp_path / "issue-97-linux-dev-environment"
    result = run(["git", "worktree", "add", "-q", "-b", "test/97", str(linked)], repository)
    assert result.returncode == 0, result.stderr
    _, env = fake_docker_environment(tmp_path)

    main_values = run_compose_script(repository, tmp_path / "main.env", env)
    linked_values = run_compose_script(linked, tmp_path / "linked.env", env)

    common_dir = str((repository / ".git").resolve())
    linked_git_dir = run(["git", "rev-parse", "--path-format=absolute", "--git-dir"], linked)
    assert linked_git_dir.returncode == 0
    relative_linked_git_dir = Path(linked_git_dir.stdout.strip()).relative_to(common_dir)

    assert main_values["SHANHAI_GIT_COMMON_DIR"] == common_dir
    assert main_values["SHANHAI_CONTAINER_GIT_DIR"] == "/git-common"
    assert linked_values["SHANHAI_GIT_COMMON_DIR"] == common_dir
    assert linked_values["SHANHAI_CONTAINER_GIT_DIR"] == (
        f"/git-common/{relative_linked_git_dir.as_posix()}"
    )
    assert linked_values["SHANHAI_WORKSPACE_UID"] == "0"
    assert linked_values["SHANHAI_WORKSPACE_GID"] == "0"
    assert linked_values["SHANHAI_CONTAINER_ROOTLESS_USERNS"] == "true"
    assert linked_values["SHANHAI_POSTGRES_PORT"] == "55529"
    assert linked_values["SHANHAI_REDIS_PORT"] == "56476"
    assert linked_values["SHANHAI_DEV_API_PORT"] == "58097"
    assert linked_values["SHANHAI_MINIO_API_PORT"] == "59097"
    assert linked_values["SHANHAI_MINIO_CONSOLE_PORT"] == "59098"
    assert main_values["SHANHAI_POSTGRES_PORT"] != linked_values["SHANHAI_POSTGRES_PORT"]


@pytest.mark.skipif(os.name != "posix", reason="Compose host routing is verified on Linux")
def test_compose_script_fails_closed_without_isolation_mode(tmp_path: Path) -> None:
    repository = tmp_path / "main-repo"
    init_repository(repository)
    _, env = fake_docker_environment(tmp_path)
    env.pop("SHANHAI_DOCKER_ISOLATION_MODE")

    result = run(
        ["bash", str(PROJECT_ROOT / "infra/dev/compose.sh"), "up", "-d"], repository, env=env
    )

    assert result.returncode != 0
    assert "SHANHAI_DOCKER_ISOLATION_MODE" in result.stderr


@pytest.mark.skipif(os.name != "posix", reason="Compose host routing is verified on Linux")
def test_compose_script_requires_audited_dedicated_host_marker(tmp_path: Path) -> None:
    repository = tmp_path / "main-repo"
    init_repository(repository)
    _, env = fake_docker_environment(tmp_path)
    marker = tmp_path / "dedicated-development-host"
    env["SHANHAI_DOCKER_ISOLATION_MODE"] = "dedicated-ecs"
    env["SHANHAI_DEDICATED_HOST_MARKER"] = str(marker)

    missing = run(
        ["bash", str(PROJECT_ROOT / "infra/dev/compose.sh"), "up", "-d"],
        repository,
        env=env,
    )
    assert missing.returncode != 0
    assert "dedicated ECS marker is missing" in missing.stderr

    marker.write_text("shanhaiedu-dedicated-development-host-v1\n", encoding="utf-8")
    values = run_compose_script(repository, tmp_path / "dedicated.env", env)
    assert values["SHANHAI_WORKSPACE_UID"] == str(os.getuid())
    assert values["SHANHAI_WORKSPACE_GID"] == str(os.getgid())
    assert values["SHANHAI_CONTAINER_ROOTLESS_USERNS"] == "false"


@pytest.mark.skipif(os.name != "posix", reason="Git wrapper scope is verified in container")
def test_git_wrapper_scopes_worktree_metadata_to_workspace(tmp_path: Path) -> None:
    project = run(["git", "rev-parse", "--show-toplevel"], PROJECT_ROOT)
    assert project.returncode == 0, project.stderr
    assert Path(project.stdout.strip()).resolve() == PROJECT_ROOT.resolve()

    temporary_repository = tmp_path / "temporary-repository"
    init_repository(temporary_repository)
    temporary = run(["git", "rev-parse", "--show-toplevel"], temporary_repository)
    assert temporary.returncode == 0, temporary.stderr
    assert Path(temporary.stdout.strip()).resolve() == temporary_repository.resolve()


@pytest.mark.skipif(os.name != "posix", reason="Linux filesystem behavior is verified in container")
def test_linux_filesystem_supports_symlinks_and_long_paths(tmp_path: Path) -> None:
    verify_filesystem(tmp_path)
    verify_workspace_write(tmp_path)
