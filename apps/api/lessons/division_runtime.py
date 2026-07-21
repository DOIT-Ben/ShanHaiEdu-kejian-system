"""Pure lesson-division validation, mapping, and stable-key diff rules."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from apps.api.artifact_quality.contracts import (
    QualityValidationContext,
    ValidatorOutcome,
    ValidatorRef,
)
from apps.api.lessons.domain import ApprovedLessonDivision, ApprovedLessonItem

LESSON_DIVISION_SCHEMA_REF = ValidatorRef(
    key="validator.lesson_division.schema",
    semantic_version="1.0.0",
    implementation_digest="983177b3209826d85693543561ff11f886ee702635a97c91514078a30bd31529",
)
LESSON_DIVISION_COVERAGE_REF = ValidatorRef(
    key="validator.lesson_division.coverage",
    semantic_version="1.0.0",
    implementation_digest="d5f63fea5edbd0f8ca4f4868a1a990826794864ec672d0dd48f6d29f7fd2bede",
)

_REQUIRED_UNIT_TEXT_FIELDS = (
    "lesson_unit_key",
    "title",
    "lesson_type",
    "core_learning_outcome",
    "material_scope",
    "prior_learning",
    "content_boundary",
    "teaching_focus",
    "learning_difficulty",
    "division_reason",
    "following_connection",
)
_UNORDERED_UNIT_LIST_FIELDS = ("evidence_refs", "must_not_preteach")
_PROTECTED_UNIT_FIELDS = tuple(
    field
    for field in (
        *_REQUIRED_UNIT_TEXT_FIELDS,
        "duration_minutes",
        *_UNORDERED_UNIT_LIST_FIELDS,
    )
    if field != "lesson_unit_key"
)


class LessonDivisionRuntimeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class LessonDivisionDiff:
    added_keys: tuple[str, ...]
    changed_keys: tuple[str, ...]
    unchanged_keys: tuple[str, ...]
    archived_keys: tuple[str, ...]

    @property
    def stale_keys(self) -> tuple[str, ...]:
        return tuple(sorted((*self.changed_keys, *self.archived_keys)))


class LessonDivisionSchemaValidator:
    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        findings = _schema_findings(context.source_content)
        return ValidatorOutcome(
            validator=LESSON_DIVISION_SCHEMA_REF,
            passed=not findings,
            findings=tuple(findings),
            evidence={
                "source_version_id": str(context.source_version_id),
                "checked_lesson_count": _lesson_count(context.source_content),
            },
        )


class LessonDivisionCoverageValidator:
    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        findings = _coverage_findings(context.source_content, context.supporting_inputs)
        return ValidatorOutcome(
            validator=LESSON_DIVISION_COVERAGE_REF,
            passed=not findings,
            findings=tuple(findings),
            evidence={
                "source_version_id": str(context.source_version_id),
                "approved_evidence_keys": sorted(
                    _approved_evidence_keys(context.supporting_inputs)
                ),
            },
        )


def build_approved_lesson_division(
    version_id: UUID,
    content: Mapping[str, Any],
) -> ApprovedLessonDivision:
    findings = _schema_findings(content)
    if findings:
        first = findings[0]
        raise LessonDivisionRuntimeError(str(first["code"]), str(first["message"]))
    units = _lesson_units(content)
    return ApprovedLessonDivision(
        version_id=version_id,
        lessons=tuple(
            ApprovedLessonItem(
                lesson_key=cast(str, unit["lesson_unit_key"]),
                position=cast(int, unit["position"]),
                title=cast(str, unit["title"]),
                scope_summary=cast(str, unit["material_scope"]),
                objective_summary=cast(str, unit["core_learning_outcome"]),
                estimated_minutes=cast(int, unit["duration_minutes"]),
            )
            for unit in sorted(units, key=lambda value: cast(int, value["position"]))
        ),
    )


def diff_lesson_divisions(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> LessonDivisionDiff:
    current_units = _units_by_key(current)
    previous_units = {} if previous is None else _units_by_key(previous)
    previous_keys = set(previous_units)
    current_keys = set(current_units)
    shared = previous_keys & current_keys
    changed = sorted(
        key
        for key in shared
        if _protected_signature(previous_units[key]) != _protected_signature(current_units[key])
    )
    unchanged = sorted(shared - set(changed))
    return LessonDivisionDiff(
        added_keys=tuple(sorted(current_keys - previous_keys)),
        changed_keys=tuple(changed),
        unchanged_keys=tuple(unchanged),
        archived_keys=tuple(sorted(previous_keys - current_keys)),
    )


def _schema_findings(content: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    units = _lesson_units(content)
    declared_count = content.get("lesson_count")
    if type(declared_count) is not int or declared_count != len(units):
        findings.append(_finding("LESSON_COUNT_MISMATCH", "lesson_count must match lesson_units"))
    if not 1 <= len(units) <= 20:
        findings.append(_finding("LESSON_COUNT_INVALID", "lesson_units must contain 1 to 20 items"))

    keys: list[str] = []
    positions: list[int] = []
    for index, unit in enumerate(units):
        unit_findings, key, position = _unit_schema_findings(unit, index)
        findings.extend(unit_findings)
        if key is not None:
            keys.append(key)
        if position is not None:
            positions.append(position)
    if len(keys) != len(set(keys)):
        findings.append(
            _finding("LESSON_UNIT_KEY_DUPLICATE", "lesson_unit_key values must be unique")
        )
    if sorted(positions) != list(range(1, len(units) + 1)):
        findings.append(
            _finding(
                "LESSON_POSITION_NON_CONTIGUOUS",
                "lesson positions must be unique and contiguous starting at one",
            )
        )
    return findings


def _unit_schema_findings(
    unit: Mapping[str, Any],
    index: int,
) -> tuple[list[dict[str, Any]], str | None, int | None]:
    findings: list[dict[str, Any]] = []
    path = f"/lesson_units/{index}"
    raw_key = unit.get("lesson_unit_key")
    key = raw_key if isinstance(raw_key, str) and raw_key.strip() and len(raw_key) <= 80 else None
    if key is None:
        findings.append(_finding("LESSON_UNIT_KEY_INVALID", "lesson_unit_key is invalid", path))
    raw_position = unit.get("position")
    position = raw_position if type(raw_position) is int and raw_position > 0 else None
    if position is None:
        findings.append(_finding("LESSON_POSITION_INVALID", "position is invalid", path))
    for field in _REQUIRED_UNIT_TEXT_FIELDS:
        value = unit.get(field)
        if type(value) is not str or not value.strip():
            code = (
                "LESSON_CORE_OUTCOME_EMPTY"
                if field == "core_learning_outcome"
                else "LESSON_FIELD_REQUIRED"
            )
            findings.append(_finding(code, f"{field} must be non-empty", f"{path}/{field}"))
    duration = unit.get("duration_minutes")
    if type(duration) is not int or not 30 <= duration <= 60:
        findings.append(
            _finding(
                "LESSON_CAPACITY_INVALID",
                "duration_minutes must be between 30 and 60",
                f"{path}/duration_minutes",
            )
        )
    for field in _UNORDERED_UNIT_LIST_FIELDS:
        values = unit.get(field)
        if not _non_empty_unique_strings(values):
            findings.append(
                _finding("LESSON_FIELD_REQUIRED", f"{field} is invalid", f"{path}/{field}")
            )
    return findings, key, position


def _coverage_findings(
    content: Mapping[str, Any],
    supporting_inputs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    approved = _approved_evidence_keys(supporting_inputs)
    referenced: list[str] = []
    for unit in _lesson_units(content):
        values = unit.get("evidence_refs")
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes, bytearray)):
            referenced.extend(
                value for value in cast(Sequence[object], values) if isinstance(value, str)
            )
    findings: list[dict[str, Any]] = []
    counts = Counter(referenced)
    duplicated = sorted(key for key, count in counts.items() if count > 1)
    out_of_scope = sorted(set(referenced) - approved)
    omitted = sorted(approved - set(referenced))
    if omitted:
        findings.append(
            _finding("MATERIAL_EVIDENCE_OMITTED", "approved evidence was not covered", keys=omitted)
        )
    if duplicated:
        findings.append(
            _finding(
                "MATERIAL_EVIDENCE_DUPLICATED",
                "approved evidence was assigned more than once",
                keys=duplicated,
            )
        )
    if out_of_scope:
        findings.append(
            _finding(
                "MATERIAL_EVIDENCE_OUT_OF_SCOPE",
                "lesson division references evidence outside the approved material",
                keys=out_of_scope,
            )
        )
    coverage = content.get("coverage_check")
    coverage_values = cast(Mapping[str, Any], coverage) if isinstance(coverage, Mapping) else None
    if coverage_values is None or coverage_values.get("all_evidence_covered") is not True:
        findings.append(
            _finding("MATERIAL_EVIDENCE_OMITTED", "coverage_check does not confirm coverage")
        )
    if coverage_values is None or coverage_values.get("overlap_free") is not True:
        findings.append(_finding("LESSON_SCOPE_OVERLAP", "coverage_check reports overlap"))
    if coverage_values is not None:
        unresolved = coverage_values.get("unresolved_questions")
        if unresolved not in ([], ()):
            findings.append(
                _finding(
                    "LESSON_SCOPE_UNRESOLVED",
                    "unresolved material questions must be resolved before approval",
                )
            )
    return findings


def _approved_evidence_keys(
    supporting_inputs: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    material = supporting_inputs.get("content:material_evidence")
    if material is None:
        return set()
    evidence = material.get("material_evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes, bytearray)):
        return set()
    keys: set[str] = set()
    for item in cast(Sequence[object], evidence):
        if not isinstance(item, Mapping):
            continue
        key = cast(Mapping[str, Any], item).get("evidence_key")
        if isinstance(key, str) and key.strip():
            keys.add(key)
    return keys


def _lesson_units(content: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    units = content.get("lesson_units")
    if not isinstance(units, Sequence) or isinstance(units, (str, bytes, bytearray)):
        return []
    return [
        cast(Mapping[str, Any], unit)
        for unit in cast(Sequence[object], units)
        if isinstance(unit, Mapping)
    ]


def _lesson_count(content: Mapping[str, Any]) -> int:
    return len(_lesson_units(content))


def _units_by_key(content: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    findings = _schema_findings(content)
    if findings:
        first = findings[0]
        raise LessonDivisionRuntimeError(str(first["code"]), str(first["message"]))
    return {cast(str, unit["lesson_unit_key"]): unit for unit in _lesson_units(content)}


def _protected_signature(unit: Mapping[str, Any]) -> str:
    values: dict[str, Any] = {}
    for field in _PROTECTED_UNIT_FIELDS:
        value = unit.get(field)
        if field in _UNORDERED_UNIT_LIST_FIELDS and isinstance(value, Sequence):
            value = sorted(cast(Sequence[str], value))
        values[field] = value
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _non_empty_unique_strings(value: object) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return False
    values = list(cast(Sequence[object], value))
    return (
        bool(values)
        and all(isinstance(item, str) and item.strip() for item in values)
        and len(set(values)) == len(values)
    )


def _finding(
    code: str,
    message: str,
    path: str | None = None,
    *,
    keys: Sequence[str] | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        finding["path"] = path
    if keys is not None:
        finding["keys"] = list(keys)
    return finding
