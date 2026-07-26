"""Two-stage candidate scoring rules for intro option generation."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any, cast

from apps.api.model_gateway.contracts import ModelCapability, TextModelRequest

_SCORING_MAX_OUTPUT_TOKENS = 12_288


class IntroOptionScoringError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def build_intro_option_scoring_request(
    *,
    prompt_template: Mapping[str, Any],
    candidates: Mapping[str, Any],
    output_schema: Mapping[str, Any],
    request_id: str,
) -> TextModelRequest:
    spec = _mapping(prompt_template.get("spec"), "published scoring prompt spec")
    try:
        capability = ModelCapability(str(spec["model_capability"]))
        sections = cast(Sequence[Mapping[str, Any]], spec["sections"])
        instructions = "\n\n".join(str(section["content"]) for section in sections)
    except (KeyError, TypeError, ValueError) as exc:
        raise IntroOptionScoringError(
            "INTRO_SCORING_PROMPT_INVALID",
            "the published scoring prompt is invalid",
        ) from exc
    candidate_json = _canonical_json(candidates)
    schema_json = _canonical_json(output_schema)
    prompt = (
        f"{instructions}\n\n"
        f"Exact candidate pool JSON:\n{candidate_json}\n\n"
        f"Required scoring output JSON Schema:\n{schema_json}\n\n"
        "Return exactly one JSON object and no commentary."
    )
    try:
        return TextModelRequest(
            capability=capability,
            request_id=request_id,
            prompt=prompt,
            max_output_tokens=_SCORING_MAX_OUTPUT_TOKENS,
            temperature=0,
        )
    except ValueError as exc:
        raise IntroOptionScoringError(
            "INTRO_SCORING_PROMPT_INVALID",
            "the scoring request exceeds the supported contract",
        ) from exc


def merge_intro_option_scores(
    candidates: Mapping[str, Any],
    scoring: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge an exact scoring result without allowing it to rewrite candidates."""

    raw_options = candidates.get("options")
    raw_evaluations = scoring.get("evaluations")
    if not _is_mapping_sequence(raw_options) or not _is_mapping_sequence(raw_evaluations):
        raise IntroOptionScoringError(
            "INTRO_SCORING_OPTION_KEYS_MISMATCH",
            "candidate and scoring option collections must be objects",
        )
    options = cast(Sequence[Mapping[str, Any]], raw_options)
    evaluations = cast(Sequence[Mapping[str, Any]], raw_evaluations)
    candidate_keys = [_option_key(option) for option in options]
    evaluation_keys = [_option_key(evaluation) for evaluation in evaluations]
    if (
        len(candidate_keys) != len(set(candidate_keys))
        or len(evaluation_keys) != len(set(evaluation_keys))
        or set(candidate_keys) != set(evaluation_keys)
    ):
        raise IntroOptionScoringError(
            "INTRO_SCORING_OPTION_KEYS_MISMATCH",
            "scoring must cover the exact candidate option keys once",
        )
    by_key = {evaluation["option_key"]: evaluation for evaluation in evaluations}
    merged = deepcopy(dict(candidates))
    merged_options = cast(list[dict[str, Any]], merged["options"])
    for option in merged_options:
        evaluation = by_key[option["option_key"]]
        option["recommendation_score"] = evaluation["recommendation_score"]
        option["recommendation_reason"] = evaluation["recommendation_reason"]
        option["risks"] = deepcopy(evaluation["risks"])
    summary = scoring.get("recommendation_summary")
    if not isinstance(summary, Mapping):
        raise IntroOptionScoringError(
            "INTRO_SCORING_RECOMMENDATION_INVALID",
            "scoring must declare one global recommendation",
        )
    typed_summary = cast(Mapping[str, object], summary)
    scores = [option.get("recommendation_score") for option in merged_options]
    if any(type(score) is not int for score in scores):
        raise IntroOptionScoringError(
            "INTRO_SCORING_RECOMMENDATION_INVALID",
            "every candidate must receive an integer score",
        )
    maximum = max(cast(list[int], scores))
    winners = [
        option["option_key"]
        for option in merged_options
        if option["recommendation_score"] == maximum
    ]
    if (
        len(winners) != 1
        or typed_summary.get("recommended_option_key") != winners[0]
        or typed_summary.get("single_highest_score") is not True
    ):
        raise IntroOptionScoringError(
            "INTRO_SCORING_RECOMMENDATION_INVALID",
            "the global recommendation must be the unique highest-scored option",
        )
    merged["recommendation_summary"] = deepcopy(dict(typed_summary))
    return merged


def _option_key(value: Mapping[str, Any]) -> str:
    key = value.get("option_key")
    if type(key) is not str or not key:
        raise IntroOptionScoringError(
            "INTRO_SCORING_OPTION_KEYS_MISMATCH",
            "every candidate and evaluation requires an option key",
        )
    return key


def _is_mapping_sequence(value: object) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return False
    return all(isinstance(item, Mapping) for item in cast(Sequence[object], value))


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IntroOptionScoringError("INTRO_SCORING_PROMPT_INVALID", f"{label} is invalid")
    return cast(Mapping[str, Any], value)


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
