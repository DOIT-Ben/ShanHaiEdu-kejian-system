from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_parallel_fixtures import (
    FIXTURE_PATH,
    validate_parallel_fixture,
)

ROOT = Path(__file__).resolve().parents[2]


def _fixture() -> dict[str, object]:
    return json.loads((ROOT / FIXTURE_PATH.relative_to(ROOT)).read_text(encoding="utf-8"))


def test_parallel_fixture_validation_passes() -> None:
    assert validate_parallel_fixture(ROOT) == []


def test_parallel_fixture_rejects_non_uuid_identity(tmp_path: Path) -> None:
    fixture = copy.deepcopy(_fixture())
    fixture["project"]["project_id"] = "PROJECT-FREEZE-001"
    fixture_path = tmp_path / "contracts/fixtures/contract-freeze"
    fixture_path.mkdir(parents=True)
    (fixture_path / "primary-math-two-lessons.json").write_text(
        json.dumps(fixture, ensure_ascii=False),
        encoding="utf-8",
    )

    for relative in (
        "contracts/fixtures/parallel-inputs/mainline/example.json",
        "contracts/fixtures/parallel-inputs/ppt/example.json",
        "contracts/fixtures/parallel-inputs/video/example.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8")

    errors = validate_parallel_fixture(tmp_path)

    assert any("project.project_id must be a canonical UUID" in error for error in errors)


def test_parallel_fixture_rejects_projection_drift(tmp_path: Path) -> None:
    for relative in (
        "contracts/fixtures/contract-freeze/primary-math-two-lessons.json",
        "contracts/fixtures/parallel-inputs/mainline/example.json",
        "contracts/fixtures/parallel-inputs/ppt/example.json",
        "contracts/fixtures/parallel-inputs/video/example.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8")

    ppt_path = tmp_path / "contracts/fixtures/parallel-inputs/ppt/example.json"
    ppt_example = json.loads(ppt_path.read_text(encoding="utf-8"))
    ppt_example["inputs"][0]["approved_lesson_plan_version_id"] = (
        "00000000-0000-4000-8000-000000000122"
    )
    ppt_path.write_text(json.dumps(ppt_example), encoding="utf-8")

    errors = validate_parallel_fixture(tmp_path)

    assert any("PPT example field approved_lesson_plan_version_id drifted" in error for error in errors)
