"""Pure decision rules for Intro selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


class IntroSelectionDecisionError(ValueError):
    """Raised when no deterministic Intro selection can be made."""


def unique_highest_option(
    options: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    scored: list[tuple[int, Mapping[str, Any]]] = []
    for option in options:
        score = option.get("recommendation_score")
        if type(score) is not int:
            raise IntroSelectionDecisionError(
                "Policy default requires integer recommendation scores."
            )
        scored.append((score, option))
    if not scored:
        raise IntroSelectionDecisionError("Policy default requires at least one option.")
    highest = max(score for score, _ in scored)
    winners = [option for score, option in scored if score == highest]
    if len(winners) != 1:
        raise IntroSelectionDecisionError(
            "Policy default requires one unique highest recommendation score."
        )
    winner = deepcopy(dict(winners[0]))
    option_key = winner.get("option_key")
    if type(option_key) is not str:
        raise IntroSelectionDecisionError("The highest-scored option has no stable option key.")
    return winner, {"option_key": option_key, "score": highest, "unique_highest": True}
