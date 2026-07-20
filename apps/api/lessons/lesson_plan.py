"""Pure lesson-plan review draft generation for the controlled #126 slice."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast

from jsonschema import Draft202012Validator

from apps.api.lessons.lesson_plan_domain import (
    ApprovedLessonPlanScope,
    LessonPlanDefinition,
    LessonPlanSliceError,
    LessonPlanValidationReport,
    ReviewableLessonPlanDraft,
    canonical_lesson_plan_hash,
    freeze_mapping,
    thaw_json,
)


class LessonPlanGenerator(Protocol):
    def generate(self, scope: ApprovedLessonPlanScope) -> dict[str, Any]: ...


class DeterministicLessonPlanFake:
    """A scripted test generator that never invokes a model provider."""

    def __init__(self, content: Mapping[str, Any]) -> None:
        self._content = freeze_mapping(content)

    def generate(self, scope: ApprovedLessonPlanScope) -> dict[str, Any]:
        del scope
        return cast(dict[str, Any], thaw_json(self._content))


class LessonPlanSliceService:
    def __init__(
        self,
        *,
        definition: LessonPlanDefinition,
        generator: LessonPlanGenerator,
    ) -> None:
        self._definition = definition
        self._generator = generator

    def generate(self, scope: ApprovedLessonPlanScope) -> ReviewableLessonPlanDraft:
        content = self._generator.generate(scope)
        report = LessonPlanBusinessValidator(self._definition).validate(scope, content)
        return ReviewableLessonPlanDraft(
            organization_id=scope.organization_id,
            project_id=scope.project_id,
            lesson_unit_id=scope.lesson_unit_id,
            approved_division_version_id=scope.approved_division_version_id,
            approved_parse_version_id=scope.material.approved_parse_version_id,
            lesson_plan_key=scope.lesson_plan_key,
            content=freeze_mapping(content),
            content_hash=canonical_lesson_plan_hash(content),
            validation_report=report,
        )


class LessonPlanBusinessValidator:
    def __init__(self, definition: LessonPlanDefinition) -> None:
        self._definition = definition

    def validate(
        self,
        scope: ApprovedLessonPlanScope,
        content: dict[str, Any],
    ) -> LessonPlanValidationReport:
        section_keys = self._section_keys()
        if set(content) != set(section_keys):
            raise LessonPlanSliceError(
                "LESSON_PLAN_SECTION_MISMATCH: content differs from definition"
            )
        self._validate_schema(content)
        teaching_content = self._mapping(content, "teaching_content")
        self._validate_teaching_content(scope, teaching_content)
        objective_keys, assessment_keys = self._validate_objectives(scope, content)
        self._validate_process(scope, content, objective_keys, assessment_keys)
        self._validate_homework(content, objective_keys)
        return LessonPlanValidationReport(
            valid=True,
            findings=(),
            section_keys=section_keys,
            checks=(
                "content_definition",
                "lesson_scope",
                "material_evidence",
                "objective_references",
                "assessment_references",
                "homework_references",
            ),
        )

    def _section_keys(self) -> tuple[str, ...]:
        raw_properties = self._definition.schema_json.get("properties")
        if not isinstance(raw_properties, Mapping):
            raise LessonPlanSliceError(
                "LESSON_PLAN_DEFINITION_INVALID: published definition must declare twelve sections"
            )
        properties = cast(Mapping[str, Any], raw_properties)
        if len(properties) != 12:
            raise LessonPlanSliceError(
                "LESSON_PLAN_DEFINITION_INVALID: published definition must declare twelve sections"
            )
        keys = tuple(properties)
        if not all(key.strip() for key in keys):
            raise LessonPlanSliceError("LESSON_PLAN_DEFINITION_INVALID: section keys are invalid")
        return keys

    def _validate_schema(self, content: dict[str, Any]) -> None:
        schema = cast(dict[str, Any], thaw_json(self._definition.schema_json))
        errors = list(
            Draft202012Validator(schema).iter_errors(content)  # pyright: ignore[reportUnknownMemberType]
        )
        if errors:
            raise LessonPlanSliceError(
                "LESSON_PLAN_SCHEMA_INVALID: generated content violates definition"
            )

    def _validate_teaching_content(
        self,
        scope: ApprovedLessonPlanScope,
        teaching_content: Mapping[str, Any],
    ) -> None:
        if teaching_content.get("lesson_plan_key") != scope.lesson_plan_key:
            raise LessonPlanSliceError(
                "LESSON_PLAN_KEY_MISMATCH: generated content changed the stable plan key"
            )
        if teaching_content.get("source_lesson_unit_key") != scope.lesson_key:
            raise LessonPlanSliceError(
                "LESSON_SCOPE_MISMATCH: generated content targets another lesson"
            )
        if teaching_content.get("duration_minutes") != scope.duration_minutes:
            raise LessonPlanSliceError(
                "LESSON_DURATION_MISMATCH: generated duration differs from lesson"
            )
        self._validate_material_scope(scope, teaching_content)

    def _validate_material_scope(
        self,
        scope: ApprovedLessonPlanScope,
        teaching_content: Mapping[str, Any],
    ) -> None:
        evidence_refs = self._strings(teaching_content.get("teaching_evidence_refs"))
        if not evidence_refs or not set(evidence_refs) <= set(scope.material.evidence_refs):
            raise LessonPlanSliceError(
                "MATERIAL_SCOPE_MISMATCH: generated content cites unavailable material evidence"
            )
        scope_text = " ".join(
            str(teaching_content.get(key, "")) for key in ("teaching_scope", "content_boundary")
        ).casefold()
        if any(term.casefold() not in scope_text for term in scope.material.required_scope_terms):
            raise LessonPlanSliceError(
                "MATERIAL_SCOPE_MISMATCH: generated content omitted required material scope"
            )
        forbidden = self._strings(teaching_content.get("must_not_preteach"))
        if not set(scope.material.must_not_preteach) <= set(forbidden):
            raise LessonPlanSliceError(
                "KNOWLEDGE_BOUNDARY_MISMATCH: generated content omitted a forbidden topic"
            )

    def _validate_objectives(
        self,
        scope: ApprovedLessonPlanScope,
        content: Mapping[str, Any],
    ) -> tuple[set[str], set[str]]:
        objectives = self._mappings(content.get("teaching_objectives"), "objectives")
        objective_keys: set[str] = set()
        assessment_keys: set[str] = set()
        for objective in objectives:
            key = objective.get("objective_key")
            evidence_refs = self._strings(objective.get("objective_evidence_refs"))
            assessments = self._strings(objective.get("assessment_evidence_keys"))
            if not isinstance(key, str) or not key.strip() or key in objective_keys:
                raise LessonPlanSliceError(
                    "OBJECTIVE_REFERENCE_INVALID: objective keys must be unique"
                )
            if not evidence_refs or not set(evidence_refs) <= set(scope.material.evidence_refs):
                raise LessonPlanSliceError(
                    "OBJECTIVE_REFERENCE_INVALID: objective evidence is outside material scope"
                )
            if not assessments:
                raise LessonPlanSliceError(
                    "ASSESSMENT_REFERENCE_INVALID: objective assessment keys are required"
                )
            objective_keys.add(key)
            assessment_keys.update(assessments)
        return objective_keys, assessment_keys

    def _validate_process(
        self,
        scope: ApprovedLessonPlanScope,
        content: Mapping[str, Any],
        objective_keys: set[str],
        assessment_keys: set[str],
    ) -> None:
        process = self._mappings(content.get("teaching_process"), "teaching process")
        total_minutes = 0
        provided_assessments: set[str] = set()
        for step in process:
            minutes = step.get("process_minutes")
            keys = self._strings(step.get("process_objective_keys"))
            provided_assessments.update(
                self._reference_keys(step.get("process_assessment_evidence"))
            )
            if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 0:
                raise LessonPlanSliceError("PROCESS_DURATION_MISMATCH: process minutes are invalid")
            if not keys or not set(keys) <= objective_keys:
                raise LessonPlanSliceError(
                    "PROCESS_REFERENCE_INVALID: process references an unknown objective"
                )
            total_minutes += minutes
        if not assessment_keys <= provided_assessments:
            raise LessonPlanSliceError(
                "ASSESSMENT_REFERENCE_INVALID: objective references unknown assessment evidence"
            )
        if total_minutes != scope.duration_minutes:
            raise LessonPlanSliceError(
                "PROCESS_DURATION_MISMATCH: process duration differs from lesson duration"
            )

    def _validate_homework(
        self,
        content: Mapping[str, Any],
        objective_keys: set[str],
    ) -> None:
        homework = self._mappings(content.get("differentiated_homework"), "homework")
        for item in homework:
            keys = self._strings(item.get("homework_objective_keys"))
            if not keys or not set(keys) <= objective_keys:
                raise LessonPlanSliceError(
                    "HOMEWORK_OBJECTIVE_REFERENCE_INVALID: homework references unknown objectives"
                )

    @staticmethod
    def _mapping(content: Mapping[str, Any], key: str) -> Mapping[str, Any]:
        value = content.get(key)
        if not isinstance(value, Mapping):
            raise LessonPlanSliceError(f"LESSON_PLAN_SECTION_MISMATCH: {key} is invalid")
        return cast(Mapping[str, Any], value)

    @staticmethod
    def _mappings(value: object, label: str) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(value, list) or not value:
            raise LessonPlanSliceError(
                f"LESSON_PLAN_SECTION_MISMATCH: {label} entries are required"
            )
        entries = cast(list[object], value)
        if any(not isinstance(entry, Mapping) for entry in entries):
            raise LessonPlanSliceError(f"LESSON_PLAN_SECTION_MISMATCH: {label} entry is invalid")
        return tuple(cast(Mapping[str, Any], entry) for entry in entries)

    @staticmethod
    def _strings(value: object) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        items = cast(list[object], value)
        if any(not isinstance(item, str) or not item.strip() for item in items):
            return ()
        return tuple(cast(str, item) for item in items)

    @classmethod
    def _reference_keys(cls, value: object) -> tuple[str, ...]:
        strings = cls._strings(value)
        if strings:
            return strings
        if not isinstance(value, list):
            return ()
        keys: list[str] = []
        for item in cast(list[object], value):
            if not isinstance(item, Mapping):
                return ()
            mapping = cast(Mapping[str, Any], item)
            key = mapping.get("evidence_key")
            if not isinstance(key, str) or not key.strip():
                return ()
            keys.append(key)
        return tuple(keys)
