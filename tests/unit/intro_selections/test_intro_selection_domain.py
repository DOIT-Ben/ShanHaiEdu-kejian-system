from __future__ import annotations

import pytest

from apps.api.intro_selections.domain import (
    IntroSelectionDecisionError,
    unique_highest_option,
)


def test_unique_highest_option_returns_frozen_evidence() -> None:
    winner, evidence = unique_highest_option(
        (
            {"option_key": "INTRO-SCI-01", "recommendation_score": 90},
            {"option_key": "INTRO-APP-01", "recommendation_score": 80},
        )
    )

    assert winner["option_key"] == "INTRO-SCI-01"
    assert evidence == {
        "option_key": "INTRO-SCI-01",
        "score": 90,
        "unique_highest": True,
    }


def test_unique_highest_option_rejects_ties() -> None:
    with pytest.raises(IntroSelectionDecisionError):
        unique_highest_option(
            (
                {"option_key": "INTRO-SCI-01", "recommendation_score": 90},
                {"option_key": "INTRO-APP-01", "recommendation_score": 90},
            )
        )
