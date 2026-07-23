from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_contract_freeze import (
    EXPECTED_NODE_SEQUENCES,
    _check_two_lesson_fixture_data,
    validate_contract_freeze,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts/fixtures/contract-freeze/primary-math-two-lessons.json"


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_full_chain_contract_freeze_passes() -> None:
    assert validate_contract_freeze(ROOT) == []


def test_freeze_covers_exact_48_node_catalog() -> None:
    assert sum(len(nodes) for nodes in EXPECTED_NODE_SEQUENCES.values()) == 48
    assert len(EXPECTED_NODE_SEQUENCES["ppt"]) == 14
    assert len(EXPECTED_NODE_SEQUENCES["video"]) == 20
    assert "audio.tts.generate" in EXPECTED_NODE_SEQUENCES["video"]
    assert "audio.subtitles.compile" in EXPECTED_NODE_SEQUENCES["video"]
    assert "video.timeline.assemble" in EXPECTED_NODE_SEQUENCES["video"]
    assert "video.final.approve" in EXPECTED_NODE_SEQUENCES["video"]


def test_two_lesson_fixture_rejects_cross_lesson_ppt_version() -> None:
    fixture = copy.deepcopy(_fixture())
    lessons = fixture["lessons"]
    lessons[0]["parallel_inputs"]["ppt"]["approved_lesson_plan_version_id"] = lessons[1][
        "lesson_plan"
    ]["artifact_version_id"]

    errors = _check_two_lesson_fixture_data(fixture)

    assert any("PPT input does not use owner lesson plan version" in error for error in errors)


def test_two_lesson_fixture_rejects_video_course_context_leak() -> None:
    fixture = copy.deepcopy(_fixture())
    fixture["lessons"][0]["parallel_inputs"]["video"]["approved_lesson_plan_version_id"] = (
        "ARTIFACT-LESSON-PLAN-VERSION-001"
    )

    errors = _check_two_lesson_fixture_data(fixture)

    assert any("video input leaks forbidden course context" in error for error in errors)


def test_two_lesson_fixture_rejects_duplicate_intro_selection() -> None:
    fixture = copy.deepcopy(_fixture())
    fixture["lessons"][1]["intro"]["selection_id"] = fixture["lessons"][0]["intro"][
        "selection_id"
    ]

    errors = _check_two_lesson_fixture_data(fixture)

    assert any("duplicate intro_selection" in error for error in errors)
