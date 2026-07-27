from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.seed_r1_material_scope_e2e import (
    _extend_acceptance_locator,  # pyright: ignore[reportPrivateUsage]
)
from scripts.seed_r1_rescue_e2e import (
    ACCEPTANCE_LOCATOR_ENV,
    ROOT,
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
