from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.check_development_lease import (
    _changed_paths,
    _parse_name_status,
    parse_development_track,
    validate_changed_paths,
)

ROOT = Path(__file__).resolve().parents[2]
LEASES = ROOT / "contracts/development-leases.json"


def _leases() -> dict[str, Any]:
    return json.loads(LEASES.read_text(encoding="utf-8"))


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_parse_development_track_from_pr_body() -> None:
    body = "## Scope\n\ndevelopment-track: `shared_contract`\n"

    assert parse_development_track(body) == "shared_contract"


def test_duplicate_development_track_declarations_are_rejected() -> None:
    body = "development-track: `frontend`\ndevelopment-track: `shared_contract`\n"

    assert parse_development_track(body) is None


def test_git_rename_parser_returns_old_and_new_paths() -> None:
    output = b"R050\0contracts/api-surface.openapi.yaml\0apps/web/api.yaml\0"

    assert _parse_name_status(output) == [
        "contracts/api-surface.openapi.yaml",
        "apps/web/api.yaml",
    ]


def test_real_git_rename_returns_old_and_new_paths(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "contract-test@example.invalid")
    _git(tmp_path, "config", "user.name", "Contract Test")
    source = tmp_path / "contracts/api-surface.openapi.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("openapi: 3.1.0\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    base_sha = _git(tmp_path, "rev-parse", "HEAD")

    target = tmp_path / "apps/web/api-surface.openapi.yaml"
    target.parent.mkdir(parents=True)
    _git(tmp_path, "mv", str(source.relative_to(tmp_path)), str(target.relative_to(tmp_path)))
    _git(tmp_path, "commit", "-m", "rename")
    head_sha = _git(tmp_path, "rev-parse", "HEAD")

    changed_paths = _changed_paths(base_sha, head_sha, tmp_path)

    assert changed_paths == [
        "contracts/api-surface.openapi.yaml",
        "apps/web/api-surface.openapi.yaml",
    ]


def test_git_type_change_parser_returns_protected_path() -> None:
    output = b"T\0contracts/api-surface.openapi.yaml\0"

    assert _parse_name_status(output) == ["contracts/api-surface.openapi.yaml"]


def test_frontend_track_accepts_web_files() -> None:
    errors = validate_changed_paths(
        _leases(),
        "frontend",
        ["apps/web/src/features/lessons/lesson-plan-page.tsx"],
    )

    assert errors == []


def test_frontend_track_rejects_active_openapi_changes() -> None:
    errors = validate_changed_paths(
        _leases(),
        "frontend",
        ["contracts/api-surface.openapi.yaml"],
    )

    assert any("cannot modify" in error for error in errors)


def test_frontend_track_rejects_protected_file_renamed_into_web() -> None:
    renamed_paths = _parse_name_status(
        b"R050\0contracts/api-surface.openapi.yaml\0apps/web/api.yaml\0"
    )

    errors = validate_changed_paths(_leases(), "frontend", renamed_paths)

    assert any("contracts/api-surface.openapi.yaml" in error for error in errors)


def test_frontend_track_rejects_protected_file_type_change() -> None:
    changed_paths = _parse_name_status(b"T\0contracts/api-surface.openapi.yaml\0")

    errors = validate_changed_paths(_leases(), "frontend", changed_paths)

    assert any("contracts/api-surface.openapi.yaml" in error for error in errors)


def test_ppt_track_accepts_real_ppt_runtime_files() -> None:
    errors = validate_changed_paths(
        _leases(),
        "ppt",
        [
            "apps/api/ppt_runtime/service.py",
            "apps/api/assets/pptx_writer.py",
            "tests/integration/test_ppt_runtime.py",
        ],
    )

    assert errors == []


def test_video_track_accepts_real_video_runtime_files() -> None:
    errors = validate_changed_paths(
        _leases(),
        "video",
        [
            "apps/api/video_runtime/service.py",
            "tests/unit/video_runtime/test_service.py",
            "tests/integration/test_video_runtime.py",
        ],
    )

    assert errors == []


def test_ppt_track_rejects_video_runtime_changes() -> None:
    errors = validate_changed_paths(
        _leases(),
        "ppt",
        ["apps/api/video_runtime/service.py"],
    )

    assert any("cannot modify" in error for error in errors)


def test_video_track_rejects_ppt_runtime_changes() -> None:
    errors = validate_changed_paths(
        _leases(),
        "video",
        ["apps/api/ppt_runtime/service.py"],
    )

    assert any("cannot modify" in error for error in errors)


def test_mainline_track_rejects_shared_node_execution_changes() -> None:
    errors = validate_changed_paths(
        _leases(),
        "mainline",
        ["apps/api/node_execution/router.py"],
    )

    assert any("cannot modify" in error for error in errors)


def test_unknown_or_unleased_paths_fail_closed() -> None:
    unknown_track_errors = validate_changed_paths(_leases(), "unknown", ["README.md"])
    unleased_path_errors = validate_changed_paths(_leases(), "video", ["README.md"])

    assert unknown_track_errors == ["unknown development track: unknown"]
    assert any("no writable lease" in error for error in unleased_path_errors)
