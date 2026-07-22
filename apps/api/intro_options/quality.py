"""Deterministic validators for published intro option-set quality reports."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, cast

from jsonschema import Draft202012Validator

from apps.api.artifact_quality.contracts import (
    QualityValidationContext,
    ValidatorOutcome,
    ValidatorRef,
)
from apps.api.artifact_quality.registry import InMemoryQualityValidatorRegistry

INTRO_OPTION_SCHEMA_REF = ValidatorRef(
    key="validator.intro.option_set_schema",
    semantic_version="1.0.0",
    implementation_digest="2049fe72e70c9c5280e011cfd131b47d7444128973c4e7163c2c51d08d18a379",
)
INTRO_SINGLE_ANCHOR_REF = ValidatorRef(
    key="validator.intro.single_anchor",
    semantic_version="1.0.0",
    implementation_digest="c32be2ad3444760ff6d7454d7bc3e7a9a3518e223931d2792fabf2980e8a36dd",
)
INTRO_UNIQUE_RECOMMENDATION_REF = ValidatorRef(
    key="validator.intro.unique_recommendation",
    semantic_version="1.0.0",
    implementation_digest="60469c797f3e35e6089fed2530bac6a3fc4a71dc17377e2325e7b3fd77468c12",
)


class IntroOptionSchemaQualityValidator:
    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        content = context.source_content
        findings = _schema_findings(context)
        mode = content.get("generation_mode")
        options = _mapping_sequence(content.get("options"))
        sources = _string_sequence(content.get("source_intro_option_version_refs"))
        expected_count = 9 if mode == "default_nine" else 1 if mode == "refine_existing" else 0
        expected_sources = 0 if mode == "default_nine" else 1 if mode == "refine_existing" else -1
        if len(options) != expected_count:
            findings.append(_finding("INTRO_OPTION_COUNT_INVALID", "option count mismatches mode"))
        if len(sources) != expected_sources:
            findings.append(
                _finding("INTRO_SOURCE_CARDINALITY_INVALID", "source count mismatches mode")
            )
        if mode == "default_nine":
            tendencies = Counter(option.get("primary_tendency") for option in options)
            has_cross_tendency = any(
                len(set(_string_sequence(option.get("secondary_tendencies")))) >= 2
                for option in options
            )
            if (
                tendencies != Counter({"science": 3, "application": 3, "story": 3})
                or not has_cross_tendency
            ):
                findings.append(
                    _finding(
                        "INTRO_TENDENCY_DISTRIBUTION_INVALID",
                        "default_nine requires three options for each primary tendency",
                    )
                )
        evidence = _string_sequence(content.get("source_material_evidence_keys"))
        if not evidence or len(evidence) != len(set(evidence)):
            findings.append(
                _finding("INTRO_MATERIAL_EVIDENCE_INVALID", "material evidence is required")
            )
        if any(_contains_preteach(option.get("creative_concept")) for option in options):
            findings.append(
                _finding("INTRO_PRETEACH_VIOLATION", "creative concept preteaches the lesson")
            )
        if any(_contains_unsafe_content(option) for option in options):
            findings.append(
                _finding("INTRO_CHILD_SAFETY_INVALID", "option contains unsafe child activity")
            )
        return _outcome(
            INTRO_OPTION_SCHEMA_REF,
            findings,
            {"generation_mode": mode, "option_count": len(options)},
        )


class IntroSingleAnchorQualityValidator:
    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        content = context.source_content
        lesson_key = context.lesson_key
        options = _mapping_sequence(content.get("options"))
        findings: list[dict[str, Any]] = []
        if (
            lesson_key is None
            or content.get("source_lesson_unit_key") != lesson_key
            or any(option.get("lesson_unit_key") != lesson_key for option in options)
        ):
            findings.append(_finding("INTRO_LESSON_ANCHOR_INVALID", "lesson anchor is not exact"))
        division = context.supporting_inputs.get("approval:lesson_division")
        material = context.supporting_inputs.get("content:material_evidence")
        raw_unit = division.get("lesson_unit") if isinstance(division, Mapping) else None
        unit = cast(Mapping[str, Any], raw_unit) if isinstance(raw_unit, Mapping) else None
        knowledge = content.get("source_knowledge_point")
        if (
            unit is None
            or unit.get("lesson_unit_key") != lesson_key
            or type(knowledge) is not str
            or not knowledge.strip()
            or any(option.get("knowledge_point") != knowledge for option in options)
        ):
            findings.append(
                _finding("INTRO_COURSE_ANCHOR_INVALID", "course anchor is inconsistent")
            )
        declared_evidence = set(_string_sequence(content.get("source_material_evidence_keys")))
        available_evidence = _material_evidence_keys(material)
        lesson_evidence: set[str] = (
            set(_string_sequence(unit.get("evidence_refs"))) if unit is not None else set()
        )
        if not declared_evidence or not lesson_evidence <= declared_evidence <= available_evidence:
            findings.append(
                _finding("INTRO_MATERIAL_EVIDENCE_INVALID", "evidence is outside frozen inputs")
            )
        return _outcome(
            INTRO_SINGLE_ANCHOR_REF,
            findings,
            {"lesson_key": lesson_key, "evidence_keys": sorted(declared_evidence)},
        )


class IntroUniqueRecommendationQualityValidator:
    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        options = _mapping_sequence(context.source_content.get("options"))
        raw_summary = context.source_content.get("recommendation_summary")
        summary = cast(Mapping[str, Any], raw_summary) if isinstance(raw_summary, Mapping) else None
        findings: list[dict[str, Any]] = []
        scores = [option.get("recommendation_score") for option in options]
        numeric = [value for value in scores if type(value) in {int, float}]
        winners: list[Mapping[str, Any]] = []
        if len(numeric) == len(options) and numeric:
            maximum = max(cast(list[int | float], numeric))
            winners = [
                option for option in options if option.get("recommendation_score") == maximum
            ]
        recommended = summary.get("recommended_option_key") if summary is not None else None
        if (
            len(winners) != 1
            or winners[0].get("option_key") != recommended
            or summary is None
            or summary.get("single_highest_score") is not True
        ):
            findings.append(
                _finding(
                    "INTRO_RECOMMENDATION_NOT_UNIQUE",
                    "the declared recommendation must be the unique highest score",
                )
            )
        return _outcome(
            INTRO_UNIQUE_RECOMMENDATION_REF,
            findings,
            {"recommended_option_key": recommended},
        )


def intro_runtime_quality_validator_registry() -> InMemoryQualityValidatorRegistry:
    return InMemoryQualityValidatorRegistry(
        {
            INTRO_OPTION_SCHEMA_REF: IntroOptionSchemaQualityValidator(),
            INTRO_SINGLE_ANCHOR_REF: IntroSingleAnchorQualityValidator(),
            INTRO_UNIQUE_RECOMMENDATION_REF: IntroUniqueRecommendationQualityValidator(),
        }
    )


def _schema_findings(context: QualityValidationContext) -> list[dict[str, Any]]:
    if not context.source_schema:
        return [_finding("INTRO_SCHEMA_INVALID", "fixed source schema is unavailable")]
    validator = cast(Any, Draft202012Validator(context.source_schema))
    errors = sorted(
        validator.iter_errors(context.source_content),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    return [
        _finding(
            "INTRO_SCHEMA_INVALID",
            error.message,
            path=[str(item) for item in error.absolute_path],
        )
        for error in errors
    ]


def _mapping_sequence(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [
        cast(Mapping[str, Any], item)
        for item in cast(Sequence[object], value)
        if isinstance(item, Mapping)
    ]


def _string_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    values = tuple(cast(Sequence[object], value))
    if any(type(item) is not str or not item.strip() for item in values):
        return ()
    return cast(tuple[str, ...], values)


def _material_evidence_keys(material: Mapping[str, Any] | None) -> set[str]:
    raw = material.get("material_evidence") if material is not None else None
    values: set[str] = set()
    for item in _mapping_sequence(raw):
        key = item.get("evidence_key")
        if type(key) is str and key.strip():
            values.add(key)
    return values


def _contains_preteach(value: object) -> bool:
    if type(value) is not str:
        return False
    normalized = value.replace(" ", "")
    return any(marker in normalized for marker in ("直接讲出", "提前讲出", "直接给出答案"))


def _contains_unsafe_content(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            _contains_unsafe_content(item) for item in cast(Mapping[object, object], value).values()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_unsafe_content(item) for item in cast(Sequence[object], value))
    if type(value) is not str:
        return False
    normalized = value.replace(" ", "")
    return any(marker in normalized for marker in ("儿童独自使用明火", "模仿危险动作", "独自攀爬"))


def _finding(code: str, message: str, **evidence: object) -> dict[str, Any]:
    value: dict[str, Any] = {"code": code, "message": message}
    value.update(evidence)
    return value


def _outcome(
    ref: ValidatorRef,
    findings: list[dict[str, Any]],
    evidence: Mapping[str, Any],
) -> ValidatorOutcome:
    return ValidatorOutcome(
        validator=ref,
        passed=not findings,
        findings=tuple(findings),
        evidence=evidence,
    )
