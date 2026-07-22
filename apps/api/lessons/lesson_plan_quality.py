"""Versioned lesson-plan validators for immutable quality reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from apps.api.artifact_quality.contracts import (
    QualityValidationContext,
    ValidatorOutcome,
    ValidatorRef,
)
from apps.api.lessons.lesson_plan import LessonPlanBusinessValidator
from apps.api.lessons.lesson_plan_domain import (
    ApprovedLessonPlanScope,
    ApprovedMaterialEvidence,
    LessonPlanDefinition,
    LessonPlanSliceError,
)

LESSON_PLAN_SCHEMA_REF = ValidatorRef(
    key="validator.lesson_plan.schema",
    semantic_version="1.0.0",
    implementation_digest="259c32cdd89294b04aa70a29f711f91d3f93e5ab6659f5c80912d4a26544e2c7",
)
LESSON_PLAN_SCOPE_REF = ValidatorRef(
    key="validator.lesson_plan.scope",
    semantic_version="1.0.0",
    implementation_digest="72de7b0aa6677502ef36f29339badaf432b37c0b0409e22236efd5b03f99b68b",
)
LESSON_PLAN_TEACHING_QUALITY_REF = ValidatorRef(
    key="validator.lesson_plan.teaching_quality",
    semantic_version="1.0.0",
    implementation_digest="10296a5dfb1da0fdd73f8be5bf04fd597b37f934ef492dbe58edd7ac58afbdf2",
)


class LessonPlanSchemaQualityValidator:
    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        validator = LessonPlanBusinessValidator(_definition(context))
        try:
            section_keys = validator.validate_schema(_content(context))
        except LessonPlanSliceError as exc:
            return _failed(LESSON_PLAN_SCHEMA_REF, exc)
        return ValidatorOutcome(
            validator=LESSON_PLAN_SCHEMA_REF,
            passed=True,
            findings=(),
            evidence={"section_keys": list(section_keys)},
        )


class LessonPlanScopeQualityValidator:
    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        try:
            scope = _scope(context)
            LessonPlanBusinessValidator(_definition(context)).validate_scope(
                scope,
                _content(context),
            )
        except LessonPlanSliceError as exc:
            return _failed(LESSON_PLAN_SCOPE_REF, exc)
        return ValidatorOutcome(
            validator=LESSON_PLAN_SCOPE_REF,
            passed=True,
            findings=(),
            evidence={
                "lesson_key": scope.lesson_key,
                "approved_division_version_id": str(scope.approved_division_version_id),
                "approved_parse_version_id": str(scope.material.approved_parse_version_id),
                "evidence_refs": list(scope.material.evidence_refs),
            },
        )


class LessonPlanTeachingQualityValidator:
    def validate(self, context: QualityValidationContext) -> ValidatorOutcome:
        try:
            scope = _scope(context)
            LessonPlanBusinessValidator(_definition(context)).validate_teaching_quality(
                scope,
                _content(context),
            )
        except LessonPlanSliceError as exc:
            return _failed(LESSON_PLAN_TEACHING_QUALITY_REF, exc)
        return ValidatorOutcome(
            validator=LESSON_PLAN_TEACHING_QUALITY_REF,
            passed=True,
            findings=(),
            evidence={
                "lesson_key": scope.lesson_key,
                "duration_minutes": scope.duration_minutes,
            },
        )


def _definition(context: QualityValidationContext) -> LessonPlanDefinition:
    if not context.source_schema:
        raise LessonPlanSliceError(
            "LESSON_PLAN_DEFINITION_INVALID: fixed source definition is unavailable"
        )
    return LessonPlanDefinition(context.source_schema)


def _content(context: QualityValidationContext) -> dict[str, Any]:
    return dict(context.source_content)


def _scope(context: QualityValidationContext) -> ApprovedLessonPlanScope:
    lesson_key = context.lesson_key
    division = context.supporting_inputs.get("approval:lesson_division")
    material = context.supporting_inputs.get("content:material_evidence")
    division_version_id = context.supporting_input_versions.get("approval:lesson_division")
    parse_version_id = context.supporting_input_versions.get("content:material_evidence")
    if (
        lesson_key is None
        or context.lesson_unit_id is None
        or division is None
        or material is None
        or division_version_id is None
        or parse_version_id is None
    ):
        raise LessonPlanSliceError(
            "LESSON_SCOPE_INVALID: exact lesson and material inputs are required"
        )
    unit = _exact_lesson(division, lesson_key)
    evidence_refs = _strings(unit.get("evidence_refs"))
    material_evidence = _material_evidence_keys(material)
    if not evidence_refs or not set(evidence_refs) <= material_evidence:
        raise LessonPlanSliceError(
            "MATERIAL_EVIDENCE_INVALID: lesson evidence is outside the exact material parse"
        )
    content = _content(context)
    raw_teaching = content.get("teaching_content")
    teaching = cast(Mapping[str, Any], raw_teaching) if isinstance(raw_teaching, Mapping) else None
    lesson_plan_key = teaching.get("lesson_plan_key") if teaching is not None else None
    if type(lesson_plan_key) is not str or not lesson_plan_key.strip():
        raise LessonPlanSliceError("LESSON_SCOPE_INVALID: lesson plan key is required")
    return ApprovedLessonPlanScope(
        organization_id=context.organization_id,
        project_id=context.project_id,
        lesson_unit_id=context.lesson_unit_id,
        lesson_plan_key=lesson_plan_key,
        lesson_key=lesson_key,
        title=_required_text(unit, "title"),
        scope_summary=_required_text(unit, "material_scope"),
        objective_summary=_required_text(unit, "core_learning_outcome"),
        duration_minutes=_required_int(unit, "duration_minutes"),
        approved_division_version_id=division_version_id,
        material=ApprovedMaterialEvidence(
            approved_parse_version_id=parse_version_id,
            evidence_refs=evidence_refs,
            required_scope_terms=(_required_text(unit, "material_scope"),),
            must_not_preteach=_strings(unit.get("must_not_preteach")),
        ),
        teacher_preferences={},
    )


def _exact_lesson(division: Mapping[str, Any], lesson_key: str) -> Mapping[str, Any]:
    raw_units = division.get("lesson_units")
    if not isinstance(raw_units, Sequence) or isinstance(raw_units, (str, bytes, bytearray)):
        raise LessonPlanSliceError("LESSON_SCOPE_INVALID: lesson division is invalid")
    matches = [
        cast(Mapping[str, Any], raw)
        for raw in cast(Sequence[object], raw_units)
        if isinstance(raw, Mapping)
        and cast(Mapping[str, Any], raw).get("lesson_unit_key") == lesson_key
    ]
    if len(matches) != 1:
        raise LessonPlanSliceError(
            "LESSON_SCOPE_INVALID: approved division has no exact target lesson"
        )
    return matches[0]


def _material_evidence_keys(material: Mapping[str, Any]) -> set[str]:
    raw = material.get("material_evidence")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return set()
    return {
        cast(str, cast(Mapping[str, Any], item).get("evidence_key"))
        for item in cast(Sequence[object], raw)
        if isinstance(item, Mapping)
        and isinstance(cast(Mapping[str, Any], item).get("evidence_key"), str)
        and cast(str, cast(Mapping[str, Any], item).get("evidence_key")).strip()
    }


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    values = tuple(cast(Sequence[object], value))
    if any(type(item) is not str or not item.strip() for item in values):
        return ()
    return cast(tuple[str, ...], values)


def _required_text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if type(item) is not str or not item.strip():
        raise LessonPlanSliceError(f"LESSON_SCOPE_INVALID: {key} is required")
    return item


def _required_int(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if type(item) is not int or item <= 0:
        raise LessonPlanSliceError(f"LESSON_SCOPE_INVALID: {key} is invalid")
    return item


def _failed(ref: ValidatorRef, error: LessonPlanSliceError) -> ValidatorOutcome:
    message = str(error)
    code, separator, detail = message.partition(":")
    return ValidatorOutcome(
        validator=ref,
        passed=False,
        findings=(
            {
                "code": code if separator else "LESSON_PLAN_INVALID",
                "message": detail.strip() if separator else message,
            },
        ),
        evidence={},
    )
