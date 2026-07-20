"""Immutable facts and review result for the controlled lesson-plan slice."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast
from uuid import UUID

_ALLOWED_TEACHER_PREFERENCES = frozenset(
    {
        "classroom_style",
        "confirmed_learner_facts",
        "resource_constraints",
        "teacher_notes",
    }
)
_FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "approved_lesson_plan",
        "course_anchor",
        "intro_selection",
        "ppt",
        "video",
    }
)


class LessonPlanSliceError(ValueError):
    """Raised before an invalid lesson-plan result becomes reviewable."""


@dataclass(frozen=True, slots=True)
class ApprovedMaterialEvidence:
    """Trusted approved material facts assembled outside this business slice."""

    approved_parse_version_id: UUID
    evidence_refs: tuple[str, ...]
    required_scope_terms: tuple[str, ...]
    must_not_preteach: tuple[str, ...]

    def __post_init__(self) -> None:
        evidence_refs = tuple(self.evidence_refs)
        scope_terms = tuple(self.required_scope_terms)
        forbidden_topics = tuple(self.must_not_preteach)
        object.__setattr__(self, "evidence_refs", evidence_refs)
        object.__setattr__(self, "required_scope_terms", scope_terms)
        object.__setattr__(self, "must_not_preteach", forbidden_topics)
        if not evidence_refs or any(not value.strip() for value in evidence_refs):
            raise LessonPlanSliceError(
                "MATERIAL_EVIDENCE_INVALID: evidence references are required"
            )
        if len(set(evidence_refs)) != len(evidence_refs):
            raise LessonPlanSliceError(
                "MATERIAL_EVIDENCE_INVALID: evidence references must be unique"
            )
        if not scope_terms or any(not value.strip() for value in scope_terms):
            raise LessonPlanSliceError(
                "MATERIAL_EVIDENCE_INVALID: required scope terms are required"
            )


@dataclass(frozen=True, slots=True)
class ApprovedLessonPlanScope:
    """Trusted tenant, lesson, approval, and teacher facts frozen by the caller."""

    organization_id: UUID
    project_id: UUID
    lesson_unit_id: UUID
    lesson_plan_key: str
    lesson_key: str
    title: str
    scope_summary: str
    objective_summary: str
    duration_minutes: int
    approved_division_version_id: UUID
    material: ApprovedMaterialEvidence
    teacher_preferences: Mapping[str, Any]

    def __post_init__(self) -> None:
        if (
            not self.lesson_plan_key.strip()
            or not self.lesson_key.strip()
            or not self.title.strip()
        ):
            raise LessonPlanSliceError("LESSON_SCOPE_INVALID: stable keys and title are required")
        if not self.scope_summary.strip() or not self.objective_summary.strip():
            raise LessonPlanSliceError("LESSON_SCOPE_INVALID: approved lesson facts are required")
        if self.duration_minutes <= 0:
            raise LessonPlanSliceError("LESSON_SCOPE_INVALID: duration must be positive")
        object.__setattr__(
            self,
            "teacher_preferences",
            freeze_teacher_preferences(self.teacher_preferences),
        )


@dataclass(frozen=True, slots=True)
class LessonPlanDefinition:
    schema_json: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "schema_json", freeze_mapping(self.schema_json))


@dataclass(frozen=True, slots=True)
class LessonPlanValidationReport:
    valid: bool
    findings: tuple[str, ...]
    section_keys: tuple[str, ...]
    checks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReviewableLessonPlanDraft:
    organization_id: UUID
    project_id: UUID
    lesson_unit_id: UUID
    approved_division_version_id: UUID
    approved_parse_version_id: UUID
    lesson_plan_key: str
    content: Mapping[str, Any]
    content_hash: str
    validation_report: LessonPlanValidationReport


def freeze_teacher_preferences(value: Mapping[str, Any]) -> Mapping[str, Any]:
    unknown = set(value) - _ALLOWED_TEACHER_PREFERENCES
    if unknown or _contains_forbidden_input(value):
        raise LessonPlanSliceError(
            "TEACHER_PREFERENCE_INPUT_FORBIDDEN: cross-business inputs are not allowed"
        )
    return freeze_mapping(value)


def _contains_forbidden_input(value: object) -> bool:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return any(
            not isinstance(key, str)
            or key in _FORBIDDEN_INPUT_KEYS
            or _contains_forbidden_input(item)
            for key, item in mapping.items()
        )
    if isinstance(value, list | tuple):
        items = cast(list[object] | tuple[object, ...], value)
        return any(_contains_forbidden_input(item) for item in items)
    return False


def freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze(item) for key, item in value.items()})


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return freeze_mapping(cast(Mapping[str, Any], value))
    if isinstance(value, list | tuple):
        items = cast(list[object] | tuple[object, ...], value)
        return tuple(_freeze(item) for item in items)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    raise LessonPlanSliceError("FROZEN_INPUT_INVALID: value is not JSON-compatible")


def thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        return {key: thaw_json(item) for key, item in mapping.items()}
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return [thaw_json(item) for item in items]
    return copy.deepcopy(value)


def canonical_lesson_plan_hash(content: Mapping[str, Any]) -> str:
    payload = json.dumps(
        cast(dict[str, Any], thaw_json(content)),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
