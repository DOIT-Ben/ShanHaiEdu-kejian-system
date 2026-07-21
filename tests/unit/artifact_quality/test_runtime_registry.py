from __future__ import annotations

import json
from pathlib import Path

from apps.api.artifact_quality.binding import resolve_quality_report_binding
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[3]
BINDING = (
    ROOT
    / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"
)


def test_runtime_registry_resolves_the_published_lesson_plan_validator_set() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(
        json.loads(BINDING.read_text(encoding="utf-8"))
    )
    binding = resolve_quality_report_binding(registered, "lesson_plan.validate")

    validators = runtime_quality_validator_registry().resolve(binding.validator_refs)

    assert len(validators) == 3

