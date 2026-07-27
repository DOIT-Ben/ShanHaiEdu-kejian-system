from __future__ import annotations

import json
from pathlib import Path

from apps.api.artifact_quality.binding import resolve_quality_report_binding
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.intro_options.quality import (
    INTRO_UNIQUE_RECOMMENDATION_REF,
)
from apps.api.intro_options.quality_legacy import (
    LEGACY_INTRO_OPTION_SCHEMA_REF,
    LEGACY_INTRO_SINGLE_ANCHOR_REF,
    PREVIOUS_INTRO_OPTION_SCHEMA_REF,
    PREVIOUS_INTRO_SINGLE_ANCHOR_REF,
)
from apps.api.lessons.lesson_plan_quality import (
    LEGACY_LESSON_PLAN_SCOPE_REF,
    LEGACY_LESSON_PLAN_TEACHING_QUALITY_REF,
    LESSON_PLAN_SCHEMA_REF,
)
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[3]
BINDING = ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"


def test_runtime_registry_resolves_the_published_lesson_plan_validator_set() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(BINDING.read_text(encoding="utf-8")))
    binding = resolve_quality_report_binding(registered, "lesson_plan.validate")

    validators = runtime_quality_validator_registry().resolve(binding.validator_refs)

    assert len(validators) == 3


def test_runtime_registry_preserves_release_1_4_validator_implementations() -> None:
    registry = runtime_quality_validator_registry()

    lesson_plan = registry.resolve(
        (
            LESSON_PLAN_SCHEMA_REF,
            LEGACY_LESSON_PLAN_SCOPE_REF,
            LEGACY_LESSON_PLAN_TEACHING_QUALITY_REF,
        )
    )
    intro = registry.resolve(
        (
            LEGACY_INTRO_OPTION_SCHEMA_REF,
            PREVIOUS_INTRO_OPTION_SCHEMA_REF,
            LEGACY_INTRO_SINGLE_ANCHOR_REF,
            PREVIOUS_INTRO_SINGLE_ANCHOR_REF,
            INTRO_UNIQUE_RECOMMENDATION_REF,
        )
    )

    assert len(lesson_plan) == 3
    assert len(intro) == 5
