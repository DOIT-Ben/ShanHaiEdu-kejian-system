from __future__ import annotations

import json
from pathlib import Path

from scripts.check_development_lease import (
    parse_development_track,
    validate_changed_paths,
)

ROOT = Path(__file__).resolve().parents[2]
LEASES = ROOT / "contracts/development-leases.json"


def _leases() -> dict[str, object]:
    return json.loads(LEASES.read_text(encoding="utf-8"))


def test_parse_development_track_from_pr_body() -> None:
    body = "## Scope\n\ndevelopment-track: `shared_contract`\n"

    assert parse_development_track(body) == "shared_contract"


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


def test_ppt_track_rejects_video_runtime_changes() -> None:
    errors = validate_changed_paths(
        _leases(),
        "ppt",
        ["apps/api/video/runtime.py"],
    )

    assert any("cannot modify" in error for error in errors)


def test_unknown_or_unleased_paths_fail_closed() -> None:
    unknown_track_errors = validate_changed_paths(_leases(), "unknown", ["README.md"])
    unleased_path_errors = validate_changed_paths(_leases(), "video", ["README.md"])

    assert unknown_track_errors == ["unknown development track: unknown"]
    assert any("no writable lease" in error for error in unleased_path_errors)
