from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from scripts.seed_r1_material_scope_e2e import (
    _extend_acceptance_locator,  # pyright: ignore[reportPrivateUsage]
)
from scripts.seed_r1_rescue_e2e import (
    ACCEPTANCE_LOCATOR_ENV,
    ROOT,
    _build_rescue_division_output,  # pyright: ignore[reportPrivateUsage]
    _extend_rescue_material_evidence,  # pyright: ignore[reportPrivateUsage]
    _write_acceptance_locator,  # pyright: ignore[reportPrivateUsage]
)


def test_seed_writes_only_exact_ids_to_an_external_acceptance_locator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "locator.json"
    project_id, lesson_id, isolation_id = uuid4(), uuid4(), uuid4()
    monkeypatch.setenv(ACCEPTANCE_LOCATOR_ENV, str(destination))

    _write_acceptance_locator(
        project_id=project_id,
        lesson_unit_id=lesson_id,
        isolation_lesson_unit_id=isolation_id,
    )

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "project_id": str(project_id),
        "lesson_unit_id": str(lesson_id),
        "isolation_lesson_unit_id": str(isolation_id),
    }


def test_rescue_division_contains_the_exact_isolation_lesson() -> None:
    source: dict[str, object] = {
        "division_key": "DIVISION-001",
        "lesson_count": 1,
        "lesson_units": [
            {
                "lesson_unit_key": "LESSON-001",
                "position": 1,
                "title": "First lesson",
                "core_learning_outcome": "First outcome",
                "material_scope": "First scope",
                "evidence_refs": ["EV-MAT-01"],
            }
        ],
    }
    case: dict[str, object] = {
        "material_evidence": [
            {
                "evidence_key": "EV-MAT-01",
                "supported_claim": "First claim",
            }
        ]
    }

    evidence_mapping = _extend_rescue_material_evidence(case)
    result = _build_rescue_division_output(source, evidence_mapping)
    units = cast(list[dict[str, object]], result["lesson_units"])
    evidence = cast(list[dict[str, object]], case["material_evidence"])

    assert source["lesson_count"] == 1
    assert result["lesson_count"] == 2
    assert [item["evidence_key"] for item in evidence] == ["EV-MAT-01", "EV-MAT-02"]
    assert [unit["lesson_unit_key"] for unit in units] == [
        "LESSON-001",
        "LESSON-RESCUE-002",
    ]
    assert units[1] == {
        "lesson_unit_key": "LESSON-RESCUE-002",
        "position": 2,
        "title": "第二课时隔离验证",
        "core_learning_outcome": "独立生成本课时教案, 不读取第一课时教案。",
        "material_scope": "使用同一教材范围验证课时级上下文隔离。",
        "evidence_refs": ["EV-MAT-02"],
    }


def test_seed_refuses_to_persist_the_acceptance_locator_in_the_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ACCEPTANCE_LOCATOR_ENV, str(ROOT / "acceptance-locator.json"))

    with pytest.raises(RuntimeError, match="outside the repository"):
        _write_acceptance_locator(
            project_id=uuid4(),
            lesson_unit_id=uuid4(),
            isolation_lesson_unit_id=uuid4(),
        )


def test_material_seed_extends_the_lesson_locator_with_the_exact_division_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "locator.json"
    lesson_project_id, lesson_id, isolation_id = uuid4(), uuid4(), uuid4()
    division_project_id = uuid4()
    monkeypatch.setenv(ACCEPTANCE_LOCATOR_ENV, str(destination))
    _write_acceptance_locator(
        project_id=lesson_project_id,
        lesson_unit_id=lesson_id,
        isolation_lesson_unit_id=isolation_id,
    )

    _extend_acceptance_locator(division_project_id)

    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "project_id": str(lesson_project_id),
        "lesson_unit_id": str(lesson_id),
        "isolation_lesson_unit_id": str(isolation_id),
        "lesson_division_project_id": str(division_project_id),
    }
