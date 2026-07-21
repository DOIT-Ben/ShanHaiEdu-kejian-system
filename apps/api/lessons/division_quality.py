"""Lesson-division checks that compare output with frozen upstream scope."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any, cast


def coverage_findings(
    content: Mapping[str, Any],
    supporting_inputs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    material_keys = _material_evidence_keys(supporting_inputs)
    approved_values = _approved_scope_evidence_keys(supporting_inputs)
    approved = set(approved_values or ())
    referenced = _referenced_evidence_keys(content)
    findings: list[dict[str, Any]] = []
    if approved_values is None or not approved <= material_keys:
        findings.append(
            _finding(
                "MATERIAL_SCOPE_EVIDENCE_INVALID",
                "approved material scope must select exact evidence from the frozen parse",
            )
        )
    counts = Counter(referenced)
    omitted = sorted(approved - set(referenced))
    duplicated = sorted(key for key, count in counts.items() if count > 1)
    out_of_scope = sorted(set(referenced) - approved)
    if omitted:
        findings.append(
            _finding("MATERIAL_EVIDENCE_OMITTED", "approved evidence was not covered", omitted)
        )
    if duplicated:
        findings.append(
            _finding(
                "MATERIAL_EVIDENCE_DUPLICATED",
                "approved evidence was assigned more than once",
                duplicated,
            )
        )
    if out_of_scope:
        findings.append(
            _finding(
                "MATERIAL_EVIDENCE_OUT_OF_SCOPE",
                "lesson division references evidence outside the approved material",
                out_of_scope,
            )
        )
    findings.extend(_coverage_assertion_findings(content))
    return findings


def approved_evidence_keys(
    supporting_inputs: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    return set(_approved_scope_evidence_keys(supporting_inputs) or ())


def teacher_constraint_findings(
    content: Mapping[str, Any],
    supporting_inputs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    scope = supporting_inputs.get("approval:material_scope")
    if scope is None or not _valid_teacher_constraints(scope):
        return [
            _finding(
                "LESSON_TEACHER_CONSTRAINTS_INVALID",
                "the frozen teacher constraints are missing or invalid",
            )
        ]
    findings: list[dict[str, Any]] = []
    if any(
        unit.get("duration_minutes") != scope["duration_minutes"] for unit in _lesson_units(content)
    ):
        findings.append(
            _finding(
                "LESSON_DURATION_CONSTRAINT_MISMATCH",
                "lesson duration must match the approved course target",
            )
        )
    if (
        scope["lesson_count_mode"] == "specified"
        and content.get("lesson_count") != scope["requested_lesson_count"]
    ):
        findings.append(
            _finding(
                "LESSON_COUNT_CONSTRAINT_MISMATCH",
                "lesson count must match the approved teacher constraint",
            )
        )
    return findings


def _referenced_evidence_keys(content: Mapping[str, Any]) -> list[str]:
    referenced: list[str] = []
    for unit in _lesson_units(content):
        values = unit.get("evidence_refs")
        if isinstance(values, Sequence) and not isinstance(values, (str, bytes, bytearray)):
            referenced.extend(
                value for value in cast(Sequence[object], values) if isinstance(value, str)
            )
    return referenced


def _coverage_assertion_findings(content: Mapping[str, Any]) -> list[dict[str, Any]]:
    coverage = content.get("coverage_check")
    values = cast(Mapping[str, Any], coverage) if isinstance(coverage, Mapping) else None
    findings: list[dict[str, Any]] = []
    if values is None or values.get("all_evidence_covered") is not True:
        findings.append(_finding("MATERIAL_EVIDENCE_OMITTED", "coverage_check is incomplete"))
    if values is None or values.get("overlap_free") is not True:
        findings.append(_finding("LESSON_SCOPE_OVERLAP", "coverage_check reports overlap"))
    if values is not None and values.get("unresolved_questions") not in ([], ()):
        findings.append(
            _finding(
                "LESSON_SCOPE_UNRESOLVED",
                "unresolved material questions must be resolved before approval",
            )
        )
    return findings


def _approved_scope_evidence_keys(
    supporting_inputs: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...] | None:
    scope = supporting_inputs.get("approval:material_scope")
    raw = None if scope is None else scope.get("approved_evidence_keys")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return None
    raw_values = tuple(cast(Sequence[object], raw))
    if any(not isinstance(value, str) or not value.strip() for value in raw_values):
        return None
    values = cast(tuple[str, ...], raw_values)
    if not values or len(set(values)) != len(values) or list(values) != sorted(values):
        return None
    return values


def _material_evidence_keys(
    supporting_inputs: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    material = supporting_inputs.get("content:material_evidence")
    evidence = None if material is None else material.get("material_evidence")
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


def _valid_teacher_constraints(scope: Mapping[str, Any]) -> bool:
    duration = scope.get("duration_minutes")
    mode = scope.get("lesson_count_mode")
    requested = scope.get("requested_lesson_count")
    preferences = scope.get("lesson_type_preferences")
    requirements = scope.get("special_requirements")
    if not isinstance(preferences, Sequence) or isinstance(preferences, (str, bytes, bytearray)):
        return False
    raw_preferences = tuple(cast(Sequence[object], preferences))
    if any(not isinstance(value, str) for value in raw_preferences):
        return False
    typed_preferences = cast(tuple[str, ...], raw_preferences)
    return bool(
        type(duration) is int
        and 30 <= duration <= 60
        and mode in {"auto", "specified"}
        and (
            (mode == "auto" and requested is None)
            or (mode == "specified" and type(requested) is int and 1 <= requested <= 20)
        )
        and len(set(typed_preferences)) == len(typed_preferences)
        and all(
            value in {"new_learning", "practice", "review", "activity"}
            for value in typed_preferences
        )
        and isinstance(requirements, str)
        and len(requirements) <= 4000
    )


def _lesson_units(content: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    units = content.get("lesson_units")
    if not isinstance(units, Sequence) or isinstance(units, (str, bytes, bytearray)):
        return []
    return [
        cast(Mapping[str, Any], unit)
        for unit in cast(Sequence[object], units)
        if isinstance(unit, Mapping)
    ]


def _finding(code: str, message: str, keys: Sequence[str] | None = None) -> dict[str, Any]:
    finding: dict[str, Any] = {"code": code, "message": message}
    if keys is not None:
        finding["keys"] = list(keys)
    return finding
