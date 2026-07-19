from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from scripts.check_linux_dev_environment import validate_versions, verify_filesystem


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
    assert "UV_PYTHON" not in environment


def test_workspace_image_exposes_pnpm_through_dedicated_corepack_shim() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dockerfile = (project_root / "infra/dev/Dockerfile").read_text(encoding="utf-8")

    assert "corepack enable pnpm --install-directory /opt/corepack" in dockerfile
    assert "PATH=/workspace/.venv/bin:/opt/corepack:" in dockerfile


@pytest.mark.skipif(os.name != "posix", reason="Linux filesystem behavior is verified in container")
def test_linux_filesystem_supports_symlinks_and_long_paths(tmp_path: Path) -> None:
    verify_filesystem(tmp_path)
