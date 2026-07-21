from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.api.artifact_quality.binding import (
    resolve_quality_report_binding,
    validator_set_hash,
)
from apps.api.artifact_quality.registry import (
    InMemoryQualityValidatorRegistry,
    QualityValidatorRegistryError,
)
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"


class FixtureValidator:
    def validate(self, context):
        raise AssertionError("not invoked by registry resolution")


def test_binding_resolves_exact_published_source_and_canonical_validator_set() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))

    binding = resolve_quality_report_binding(registered, "lesson.division.validate")

    assert binding.source_input_ref == "artifact:lesson_division"
    assert [item.key for item in binding.validator_refs] == [
        "validator.lesson_division.coverage",
        "validator.lesson_division.schema",
    ]
    assert binding.validator_set_hash == validator_set_hash(binding.validator_refs)


def test_callable_registry_requires_the_exact_versioned_descriptor() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))
    binding = resolve_quality_report_binding(registered, "lesson.division.validate")
    first = binding.validator_refs[0]
    registry = InMemoryQualityValidatorRegistry({first: FixtureValidator()})

    assert len(registry.resolve((first,))) == 1
    with pytest.raises(QualityValidatorRegistryError) as captured:
        registry.resolve(binding.validator_refs)

    assert captured.value.code == "QUALITY_VALIDATOR_UNAVAILABLE"
