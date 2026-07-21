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

_VALIDATORS: dict[ValidatorRef, QualityValidator] = {
    LESSON_DIVISION_SCHEMA_REF: LessonDivisionSchemaValidator(),
    LESSON_DIVISION_COVERAGE_REF: LessonDivisionCoverageValidator(),
}


def register_runtime_quality_validator(ref: ValidatorRef, validator: QualityValidator) -> None:
    if ref in _VALIDATORS:
        raise ValueError(f"quality validator is already registered: {ref.key}")
    _VALIDATORS[ref] = validator


def runtime_quality_validator_registry() -> InMemoryQualityValidatorRegistry:
    return InMemoryQualityValidatorRegistry(_VALIDATORS)
