"""Process-local composition registry for reviewed quality validators."""

from __future__ import annotations

from apps.api.artifact_quality.contracts import QualityValidator, ValidatorRef
from apps.api.artifact_quality.registry import InMemoryQualityValidatorRegistry
from apps.api.intro_options.quality import (
    INTRO_OPTION_SCHEMA_REF,
    INTRO_SINGLE_ANCHOR_REF,
    INTRO_UNIQUE_RECOMMENDATION_REF,
    IntroOptionSchemaQualityValidator,
    IntroSingleAnchorQualityValidator,
    IntroUniqueRecommendationQualityValidator,
)
from apps.api.intro_options.quality_legacy import (
    LEGACY_INTRO_OPTION_SCHEMA_REF,
    LEGACY_INTRO_SINGLE_ANCHOR_REF,
    PREVIOUS_INTRO_OPTION_SCHEMA_REF,
    PREVIOUS_INTRO_SINGLE_ANCHOR_REF,
)
from apps.api.lessons.division_runtime import (
    LESSON_DIVISION_COVERAGE_REF,
    LESSON_DIVISION_SCHEMA_REF,
    LessonDivisionCoverageValidator,
    LessonDivisionSchemaValidator,
)
from apps.api.lessons.lesson_plan_quality import (
    LEGACY_LESSON_PLAN_SCOPE_REF,
    LEGACY_LESSON_PLAN_TEACHING_QUALITY_REF,
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
    LEGACY_LESSON_PLAN_SCOPE_REF: LessonPlanScopeQualityValidator(
        ref=LEGACY_LESSON_PLAN_SCOPE_REF,
        include_page_evidence=False,
    ),
    LEGACY_LESSON_PLAN_TEACHING_QUALITY_REF: LessonPlanTeachingQualityValidator(
        ref=LEGACY_LESSON_PLAN_TEACHING_QUALITY_REF,
        include_page_evidence=False,
    ),
    INTRO_OPTION_SCHEMA_REF: IntroOptionSchemaQualityValidator(),
    PREVIOUS_INTRO_OPTION_SCHEMA_REF: IntroOptionSchemaQualityValidator(
        ref=PREVIOUS_INTRO_OPTION_SCHEMA_REF,
        require_cross_tendency=True,
    ),
    INTRO_SINGLE_ANCHOR_REF: IntroSingleAnchorQualityValidator(),
    PREVIOUS_INTRO_SINGLE_ANCHOR_REF: IntroSingleAnchorQualityValidator(
        ref=PREVIOUS_INTRO_SINGLE_ANCHOR_REF,
        scan_teacher_fit_reason=True,
    ),
    INTRO_UNIQUE_RECOMMENDATION_REF: IntroUniqueRecommendationQualityValidator(),
    LEGACY_INTRO_OPTION_SCHEMA_REF: IntroOptionSchemaQualityValidator(
        ref=LEGACY_INTRO_OPTION_SCHEMA_REF,
        enforce_default_nine_identity=False,
        require_cross_tendency=True,
    ),
    LEGACY_INTRO_SINGLE_ANCHOR_REF: IntroSingleAnchorQualityValidator(
        ref=LEGACY_INTRO_SINGLE_ANCHOR_REF,
        include_page_evidence=False,
        scan_teacher_fit_reason=True,
    ),
}


def register_runtime_quality_validator(ref: ValidatorRef, validator: QualityValidator) -> None:
    if ref in _VALIDATORS:
        raise ValueError(f"quality validator is already registered: {ref.key}")
    _VALIDATORS[ref] = validator


def runtime_quality_validator_registry() -> InMemoryQualityValidatorRegistry:
    return InMemoryQualityValidatorRegistry(_VALIDATORS)
