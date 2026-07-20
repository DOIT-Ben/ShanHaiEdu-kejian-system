from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast
from uuid import UUID

import pytest

from apps.api.content_runtime.definition_projection import build_content_json_schema
from apps.api.lessons.lesson_plan import (
    DeterministicLessonPlanFake,
    LessonPlanSliceService,
)
from apps.api.lessons.lesson_plan_domain import (
    ApprovedLessonPlanScope,
    ApprovedMaterialEvidence,
    LessonPlanDefinition,
    LessonPlanSliceError,
    ReviewableLessonPlanDraft,
)

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "contracts/fixtures/primary-math-courseware-package"


def _unknown_assessment(content: dict[str, Any]) -> None:
    objectives = cast(list[dict[str, Any]], content["teaching_objectives"])
    objectives[0]["assessment_evidence_keys"] = ["ASSESSMENT-UNKNOWN"]


def _unknown_homework_objective(content: dict[str, Any]) -> None:
    homework = cast(list[dict[str, Any]], content["differentiated_homework"])
    homework[0]["homework_objective_keys"] = ["OBJ-UNKNOWN"]


def _missing_material_scope(content: dict[str, Any]) -> None:
    teaching_content = cast(dict[str, Any], content["teaching_content"])
    teaching_content["teaching_scope"] = "unrelated material scope"
    teaching_content["content_boundary"] = "unrelated boundary"


def _wrong_lesson_plan_key(content: dict[str, Any]) -> None:
    teaching_content = cast(dict[str, Any], content["teaching_content"])
    teaching_content["lesson_plan_key"] = "LESSON-PLAN-OTHER"


def _unknown_process_objective(content: dict[str, Any]) -> None:
    process = cast(list[dict[str, Any]], content["teaching_process"])
    process[0]["process_objective_keys"] = ["OBJ-UNKNOWN"]


def test_slice_returns_a_pure_reviewable_draft_with_canonical_hash_and_report() -> None:
    content = _valid_content()
    service = LessonPlanSliceService(
        definition=_published_lesson_plan_definition(),
        generator=DeterministicLessonPlanFake(content),
    )

    draft = service.generate(_request())

    assert isinstance(draft, ReviewableLessonPlanDraft)
    assert draft.organization_id == _request().organization_id
    assert draft.project_id == _request().project_id
    assert draft.lesson_unit_id == _request().lesson_unit_id
    assert draft.approved_division_version_id == _request().approved_division_version_id
    assert draft.approved_parse_version_id == _request().material.approved_parse_version_id
    assert draft.lesson_plan_key == "LESSON-PLAN-001"
    assert draft.content_hash == _canonical_hash(content)
    assert draft.validation_report.valid is True
    assert draft.validation_report.findings == ()
    assert len(draft.validation_report.section_keys) == 12
    assert {
        "artifact_key",
        "artifact_type",
        "branch_key",
        "content_definition_version_id",
    }.isdisjoint({field.name for field in fields(draft)})


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (_unknown_assessment, "ASSESSMENT_REFERENCE_INVALID"),
        (_unknown_homework_objective, "HOMEWORK_OBJECTIVE_REFERENCE_INVALID"),
        (_missing_material_scope, "MATERIAL_SCOPE_MISMATCH"),
        (_wrong_lesson_plan_key, "LESSON_PLAN_KEY_MISMATCH"),
        (_unknown_process_objective, "PROCESS_REFERENCE_INVALID"),
    ],
)
def test_slice_rejects_unknown_cross_references_and_scope_drift(
    mutate: Callable[[dict[str, Any]], None],
    code: str,
) -> None:
    content = _valid_content()
    mutate(content)
    service = LessonPlanSliceService(
        definition=_published_lesson_plan_definition(),
        generator=DeterministicLessonPlanFake(content),
    )

    with pytest.raises(LessonPlanSliceError, match=code):
        service.generate(_request())


def test_slice_rejects_unavailable_material_evidence_and_duration_drift() -> None:
    content = _valid_content()
    content["teaching_content"]["teaching_evidence_refs"] = ["EV-MAT-OTHER"]
    service = LessonPlanSliceService(
        definition=_published_lesson_plan_definition(),
        generator=DeterministicLessonPlanFake(content),
    )
    with pytest.raises(LessonPlanSliceError, match="MATERIAL_SCOPE_MISMATCH"):
        service.generate(_request())

    content = _valid_content()
    content["teaching_process"][0]["process_minutes"] = 6
    service = LessonPlanSliceService(
        definition=_published_lesson_plan_definition(),
        generator=DeterministicLessonPlanFake(content),
    )
    with pytest.raises(LessonPlanSliceError, match="PROCESS_DURATION_MISMATCH"):
        service.generate(_request())


@pytest.mark.parametrize("forbidden_key", ["intro_selection", "ppt", "video"])
def test_frozen_input_rejects_cross_business_teacher_preferences(forbidden_key: str) -> None:
    with pytest.raises(LessonPlanSliceError, match="TEACHER_PREFERENCE_INPUT_FORBIDDEN"):
        _request(teacher_preferences={forbidden_key: {"key": "forbidden"}})


def test_frozen_inputs_and_reviewable_result_are_deeply_immutable() -> None:
    raw_preferences = {"resource_constraints": {"available": ["number cards"]}}
    scope = _request(teacher_preferences=raw_preferences)
    raw_preferences["resource_constraints"]["available"].append("blocks")

    constraints = scope.teacher_preferences["resource_constraints"]
    assert isinstance(scope.teacher_preferences, MappingProxyType)
    assert isinstance(constraints, MappingProxyType)
    assert constraints["available"] == ("number cards",)
    with pytest.raises(TypeError):
        scope.teacher_preferences["classroom_style"] = "lecture"  # type: ignore[index]

    draft = LessonPlanSliceService(
        definition=_published_lesson_plan_definition(),
        generator=DeterministicLessonPlanFake(_valid_content()),
    ).generate(scope)
    teaching_content = draft.content["teaching_content"]
    assert isinstance(teaching_content, MappingProxyType)
    with pytest.raises(TypeError):
        teaching_content["duration_minutes"] = 45  # type: ignore[index]


def test_slice_requires_the_published_definition_to_declare_exactly_twelve_sections() -> None:
    schema = _published_lesson_plan_schema()
    properties = cast(dict[str, Any], schema["properties"])
    properties.pop("teaching_reflection")
    service = LessonPlanSliceService(
        definition=LessonPlanDefinition(schema_json=schema),
        generator=DeterministicLessonPlanFake(_valid_content()),
    )

    with pytest.raises(LessonPlanSliceError, match="LESSON_PLAN_DEFINITION_INVALID"):
        service.generate(_request())


def _request(
    *,
    teacher_preferences: dict[str, Any] | None = None,
) -> ApprovedLessonPlanScope:
    return ApprovedLessonPlanScope(
        organization_id=UUID("01930000-0000-7000-8000-000000000100"),
        project_id=UUID("01930000-0000-7000-8000-000000000101"),
        lesson_unit_id=UUID("01930000-0000-7000-8000-000000000102"),
        lesson_plan_key="LESSON-PLAN-001",
        lesson_key="LESSON-001",
        title="Numbers one to five",
        scope_summary="Connect quantities, dots, and numerals.",
        objective_summary="Represent numbers in several ways.",
        duration_minutes=40,
        approved_division_version_id=UUID("01930000-0000-7000-8000-000000000103"),
        material=ApprovedMaterialEvidence(
            approved_parse_version_id=UUID("01930000-0000-7000-8000-000000000104"),
            evidence_refs=("EV-MAT-01", "EV-MAT-02", "EV-MAT-03", "EV-MAT-04"),
            required_scope_terms=("numbers-1-to-5",),
            must_not_preteach=("比较大小", "第几", "分与合", "加法", "减法", "0的认识"),
        ),
        teacher_preferences=teacher_preferences or {"classroom_style": "hands_on"},
    )


def _published_lesson_plan_definition() -> LessonPlanDefinition:
    return LessonPlanDefinition(schema_json=_published_lesson_plan_schema())


def _published_lesson_plan_schema() -> dict[str, Any]:
    output = cast(
        dict[str, Any],
        json.loads(
            (PACKAGE / "items/lesson-plan-generate-output.json").read_text(encoding="utf-8")
        ),
    )
    spec = cast(dict[str, Any], output["spec"])
    return build_content_json_schema(spec)


def _valid_content() -> dict[str, Any]:
    definition = _published_lesson_plan_definition()
    content = _example_from_schema(dict(definition.schema_json))
    teaching_content = cast(dict[str, Any], content["teaching_content"])
    teaching_content.update(
        lesson_plan_key="LESSON-PLAN-001",
        source_lesson_unit_key="LESSON-001",
        duration_minutes=40,
        teaching_scope="numbers-1-to-5 material scope",
        teaching_evidence_refs=["EV-MAT-01", "EV-MAT-02"],
        content_boundary="numbers-1-to-5 only",
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
        entry["process_objective_keys"] = ["OBJ-001"]
        entry["process_assessment_evidence"] = ["ASSESSMENT-001"]
        entry["process_minutes"] = 0
    process[0]["process_minutes"] = 40
    homework = cast(list[dict[str, Any]], content["differentiated_homework"])
    assert homework
    for entry in homework:
        entry["homework_objective_keys"] = ["OBJ-001"]
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


def _canonical_hash(content: dict[str, Any]) -> str:
    payload = json.dumps(
        content,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
