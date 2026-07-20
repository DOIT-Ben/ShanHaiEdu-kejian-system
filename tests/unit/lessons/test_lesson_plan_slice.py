from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from apps.api.content_runtime.definition_projection import build_content_json_schema
from apps.api.lessons.lesson_plan import (
    ApprovedLessonPlanScope,
    ApprovedMaterialEvidence,
    DeterministicLessonPlanFake,
    LessonPlanDefinition,
    LessonPlanSliceError,
    LessonPlanSliceService,
)

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "contracts/fixtures/primary-math-courseware-package"


class CapturingArtifactPort:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, project_id: UUID, **kwargs: object) -> object:
        self.calls.append({"project_id": project_id, **kwargs})
        return {"id": uuid4(), "status": "draft"}


def test_slice_generates_a_reviewable_draft_for_only_the_target_lesson() -> None:
    port = CapturingArtifactPort()
    service = LessonPlanSliceService(
        definition=_published_lesson_plan_definition(),
        artifact_port=port,
        generator=DeterministicLessonPlanFake(_valid_content()),
    )

    artifact = cast(dict[str, object], service.generate(_request()))

    assert artifact["status"] == "draft"
    assert len(port.calls) == 1
    call = port.calls[0]
    assert call["artifact_key"] == "lesson-plan:LESSON-001"
    assert call["artifact_type"] == "lesson_plan"
    assert call["branch_key"] == "lesson_plan"
    assert call["draft_branch"] == "generated"
    assert call["lesson_unit_id"] == _request().lesson_unit_id
    assert call["initial_content"] == _valid_content()


def test_slice_rejects_an_unapproved_or_mismatched_input_before_creating_an_artifact() -> None:
    port = CapturingArtifactPort()
    request = _request()
    service = LessonPlanSliceService(
        definition=_published_lesson_plan_definition(),
        artifact_port=port,
        generator=DeterministicLessonPlanFake(_valid_content()),
    )

    with pytest.raises(LessonPlanSliceError, match="MATERIAL_SCOPE_MISMATCH"):
        service.generate(
            request.with_material(
                ApprovedMaterialEvidence(
                    project_id=request.project_id,
                    approved_parse_version_id=uuid4(),
                    evidence_refs=("EV-MAT-OTHER",),
                    required_scope_terms=("numbers-1-to-5",),
                    must_not_preteach=("加法",),
                )
            )
        )

    assert port.calls == []


def test_slice_rejects_duration_and_objective_reference_failures_before_persisting() -> None:
    content = _valid_content()
    content["teaching_process"][0]["process_minutes"] = 6
    port = CapturingArtifactPort()
    service = LessonPlanSliceService(
        definition=_published_lesson_plan_definition(),
        artifact_port=port,
        generator=DeterministicLessonPlanFake(content),
    )

    with pytest.raises(LessonPlanSliceError, match="PROCESS_DURATION_MISMATCH"):
        service.generate(_request())

    assert port.calls == []


def test_slice_requires_the_published_definition_to_declare_exactly_twelve_sections() -> None:
    definition = _published_lesson_plan_definition()
    schema = copy.deepcopy(definition.schema_json)
    schema["properties"].pop("teaching_reflection")
    port = CapturingArtifactPort()
    service = LessonPlanSliceService(
        definition=LessonPlanDefinition(id=definition.id, schema_json=schema),
        artifact_port=port,
        generator=DeterministicLessonPlanFake(_valid_content()),
    )

    with pytest.raises(LessonPlanSliceError, match="LESSON_PLAN_DEFINITION_INVALID"):
        service.generate(_request())

    assert port.calls == []


def _request() -> ApprovedLessonPlanScope:
    project_id = UUID("01930000-0000-7000-8000-000000000101")
    return ApprovedLessonPlanScope(
        project_id=project_id,
        lesson_unit_id=UUID("01930000-0000-7000-8000-000000000102"),
        lesson_key="LESSON-001",
        title="Numbers one to five",
        scope_summary="Connect quantities, dots, and numerals.",
        objective_summary="Represent numbers in several ways.",
        duration_minutes=40,
        approved_division_version_id=UUID("01930000-0000-7000-8000-000000000103"),
        material=ApprovedMaterialEvidence(
            project_id=project_id,
            approved_parse_version_id=UUID("01930000-0000-7000-8000-000000000104"),
            evidence_refs=("EV-MAT-01", "EV-MAT-02", "EV-MAT-03", "EV-MAT-04"),
            required_scope_terms=("numbers-1-to-5",),
            must_not_preteach=("比较大小", "第几", "分与合", "加法", "减法", "0的认识"),
        ),
        teacher_preferences={"classroom_style": "hands_on"},
    )


def _published_lesson_plan_definition() -> LessonPlanDefinition:
    output = cast(
        dict[str, Any],
        json.loads(
            (PACKAGE / "items/lesson-plan-generate-output.json").read_text(encoding="utf-8")
        ),
    )
    spec = cast(dict[str, Any], output["spec"])
    return LessonPlanDefinition(id=uuid4(), schema_json=build_content_json_schema(spec))


def _valid_content() -> dict[str, Any]:
    definition = _published_lesson_plan_definition()
    content = _example_from_schema(definition.schema_json)
    teaching_content = cast(dict[str, Any], content["teaching_content"])
    teaching_content.update(
        lesson_plan_key="lesson-plan:LESSON-001",
        source_lesson_unit_key="LESSON-001",
        duration_minutes=40,
        teaching_evidence_refs=["EV-MAT-01", "EV-MAT-02"],
        must_not_preteach=["比较大小", "第几", "分与合", "加法", "减法", "0的认识"],
    )
    objectives = cast(list[dict[str, Any]], content["teaching_objectives"])
    assert objectives
    objectives[0].update(
        objective_key="OBJ-001",
        objective_evidence_refs=["EV-MAT-01"],
        assessment_evidence_keys=["ASSESSMENT-001"],
    )
    process = cast(list[dict[str, Any]], content["teaching_process"])
    assert process
    for entry in process:
        assert isinstance(entry, dict)
        entry["process_objective_keys"] = ["OBJ-001"]
        entry["process_minutes"] = 0
    process[0]["process_minutes"] = 40
    return content


def _example_from_schema(schema: dict[str, Any]) -> dict[str, Any]:
    value = _example_value(schema)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _example_value(schema: dict[str, Any]) -> object:
    if "enum" in schema:
        return schema["enum"][0]
    if schema.get("type") == "object":
        properties = cast(dict[str, dict[str, Any]], schema.get("properties", {}))
        required = cast(list[str], schema.get("required", []))
        return {key: _example_value(properties[key]) for key in required}
    if schema.get("type") == "array":
        count = int(schema.get("minItems", 0))
        items = cast(dict[str, Any], schema.get("items", {}))
        return [_example_value(items) for _ in range(max(1, count))]
    if schema.get("type") == "number":
        return schema.get("minimum", 1)
    if schema.get("type") == "boolean":
        return True
    if schema.get("type") == "string":
        minimum = int(schema.get("minLength", 1))
        return "x" * max(1, minimum)
    if "type" not in schema and "anyOf" not in schema:
        return "x"
    alternatives = cast(list[dict[str, Any]], schema.get("anyOf", []))
    assert alternatives
    return _example_value(alternatives[0])
