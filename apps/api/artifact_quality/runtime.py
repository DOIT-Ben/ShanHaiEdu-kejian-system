"""Process-local composition registry for reviewed quality validators."""

from __future__ import annotations

from apps.api.artifact_quality.contracts import QualityValidator, ValidatorRef
from apps.api.artifact_quality.registry import InMemoryQualityValidatorRegistry
from apps.api.lessons.division_runtime import (
    LESSON_DIVISION_COVERAGE_REF,
    LESSON_DIVISION_SCHEMA_REF,
    LessonDivisionCoverageValidator,
    LessonDivisionSchemaValidator,
)
from apps.api.lessons.lesson_plan_quality import (
    LESSON_PLAN_SCHEMA_REF,
    LESSON_PLAN_SCOPE_REF,
    LESSON_PLAN_TEACHING_QUALITY_REF,
    LessonPlanSchemaQualityValidator,
    LessonPlanScopeQualityValidator,
    LessonPlanTeachingQualityValidator,
)

_VALIDATORS: dict[ValidatorRef, QualityValidator] = {
    LESSON_DIVISION_SCHEMA_REF: LessonDivisionSchemaValidator(),
    LESSON_DIVISION_COVERAGE_REF: LessonDivisionCoverageValidator(),
    LESSON_PLAN_SCHEMA_REF: LessonPlanSchemaQualityValidator(),
    LESSON_PLAN_SCOPE_REF: LessonPlanScopeQualityValidator(),
    LESSON_PLAN_TEACHING_QUALITY_REF: LessonPlanTeachingQualityValidator(),
}


def register_runtime_quality_validator(ref: ValidatorRef, validator: QualityValidator) -> None:
    if ref in _VALIDATORS:
        raise ValueError(f"quality validator is already registered: {ref.key}")
    _VALIDATORS[ref] = validator


def runtime_quality_validator_registry() -> InMemoryQualityValidatorRegistry:
    return InMemoryQualityValidatorRegistry(_VALIDATORS)
