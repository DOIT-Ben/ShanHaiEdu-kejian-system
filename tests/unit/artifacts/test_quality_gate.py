from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.api.artifacts.quality_gate import (
    ArtifactQualityGateError,
    resolve_declared_quality_gate,
)
from workflow.registry import BUILTIN_WORKFLOW_REGISTRY

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "contracts/fixtures/workflow-node-generation-bindings/primary-math-courseware.json"


def test_report_gate_resolves_exact_validate_node_and_validator_set() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))

    gate = resolve_declared_quality_gate(registered, "lesson.division.generate.output")

    assert gate is not None
    assert gate.validate_node_key == "lesson.division.validate"
    assert (
        gate.validator_set_hash
        == "d8dfb5a5cc611a55993a44c5ee27a6e3018aa75fffe68ea3d77f424fcbb1a7d2"
    )
    assert gate.accepted_conclusions == ("passed",)


def test_explicit_none_gate_preserves_approval_semantics() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))

    assert resolve_declared_quality_gate(registered, "ppt.outline.generate.output") is None


def test_current_workflow_missing_output_declaration_fails_closed() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(json.loads(CATALOG.read_text(encoding="utf-8")))

    with pytest.raises(ArtifactQualityGateError) as captured:
        resolve_declared_quality_gate(registered, "missing.output.definition")

    assert captured.value.code == "ARTIFACT_QUALITY_GATE_UNDECLARED"


def test_legacy_workflow_without_versioned_quality_declaration_fails_closed() -> None:
    registered = BUILTIN_WORKFLOW_REGISTRY.load(
        {
            "api_version": "shanhai.workflow-node-generation-binding/v1",
            "nodes": [],
        }
    )

    with pytest.raises(ArtifactQualityGateError) as captured:
        resolve_declared_quality_gate(registered, "legacy.output")

    assert captured.value.code == "ARTIFACT_QUALITY_GATE_UNDECLARED"
