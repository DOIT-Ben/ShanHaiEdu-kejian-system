from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from apps.api.intro_options.generation_pipeline import (
    IntroOptionScoringError,
    merge_intro_option_scores,
)


def _candidates() -> dict[str, Any]:
    options = []
    for prefix, tendency in (("SCI", "science"), ("APP", "application"), ("STO", "story")):
        for position in range(1, 4):
            key = f"INTRO-{prefix}-{position:02d}"
            options.append(
                {
                    "option_key": key,
                    "lesson_unit_key": "LESSON-001",
                    "knowledge_point": "1-5的认识",
                    "primary_tendency": tendency,
                    "title": f"方案 {key}",
                    "creative_concept": f"创意 {key}",
                    "hook": f"钩子 {key}",
                    "viewer_value": f"价值 {key}",
                    "suggested_medium": "video",
                    "duration_seconds": 90,
                    "course_anchor": f"锚点 {key}",
                    "classroom_first_question": f"问题 {key}",
                    "handoff_moment": f"交接 {key}",
                    "must_not_preteach": ["不提前给出结论"],
                    "fit_reason": f"适配 {key}",
                }
            )
    return {
        "option_set_key": "INTRO-SET-001",
        "generation_mode": "default_nine",
        "source_intro_option_version_refs": [],
        "source_lesson_unit_key": "LESSON-001",
        "source_knowledge_point": "1-5的认识",
        "source_material_evidence_keys": ["p2-text-1"],
        "options": options,
    }


def _scores(candidates: dict[str, Any]) -> dict[str, Any]:
    evaluations = []
    for position, option in enumerate(candidates["options"]):
        evaluations.append(
            {
                "option_key": option["option_key"],
                "recommendation_score": 100 - position,
                "recommendation_reason": f"推荐理由 {option['option_key']}",
                "risks": [f"适配风险 {option['option_key']}"],
            }
        )
    return {
        "evaluations": evaluations,
        "recommendation_summary": {
            "recommended_option_key": evaluations[0]["option_key"],
            "single_highest_score": True,
        },
    }


def test_merges_independent_scores_without_mutating_candidate_content() -> None:
    candidates = _candidates()
    original = deepcopy(candidates)

    merged = merge_intro_option_scores(candidates, _scores(candidates))

    assert candidates == original
    assert [option["option_key"] for option in merged["options"]] == [
        option["option_key"] for option in original["options"]
    ]
    for original_option, merged_option in zip(original["options"], merged["options"], strict=True):
        assert {
            key: value
            for key, value in merged_option.items()
            if key not in {"recommendation_score", "recommendation_reason", "risks"}
        } == original_option
        assert "secondary_tendencies" not in merged_option


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate"])
def test_rejects_any_scoring_key_set_that_is_not_the_exact_candidate_pool(mutation: str) -> None:
    candidates = _candidates()
    scores = _scores(candidates)
    if mutation == "missing":
        scores["evaluations"].pop()
    elif mutation == "extra":
        scores["evaluations"].append(
            {
                "option_key": "INTRO-SCI-99",
                "recommendation_score": 1,
                "recommendation_reason": "不属于候选池",
                "risks": ["无效候选"],
            }
        )
    else:
        scores["evaluations"][1]["option_key"] = scores["evaluations"][0]["option_key"]

    with pytest.raises(IntroOptionScoringError) as caught:
        merge_intro_option_scores(candidates, scores)

    assert caught.value.code == "INTRO_SCORING_OPTION_KEYS_MISMATCH"


def test_rejects_a_global_recommendation_that_disagrees_with_the_unique_highest_score() -> None:
    candidates = _candidates()
    scores = _scores(candidates)
    scores["recommendation_summary"]["recommended_option_key"] = scores["evaluations"][1][
        "option_key"
    ]

    with pytest.raises(IntroOptionScoringError) as caught:
        merge_intro_option_scores(candidates, scores)

    assert caught.value.code == "INTRO_SCORING_RECOMMENDATION_INVALID"
