"""Frozen-port lesson-plan draft generation for the controlled #126 slice."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Protocol, cast
from uuid import UUID

from jsonschema import Draft202012Validator


class LessonPlanSliceError(ValueError):
    """Raised before a generated lesson-plan draft reaches artifact persistence."""


@dataclass(frozen=True, slots=True)
class ApprovedMaterialEvidence:
    project_id: UUID
    approved_parse_version_id: UUID
    evidence_refs: tuple[str, ...]
    required_scope_terms: tuple[str, ...]
    must_not_preteach: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.evidence_refs or any(not value.strip() for value in self.evidence_refs):
            raise LessonPlanSliceError(
                "MATERIAL_EVIDENCE_INVALID: evidence references are required"
            )
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise LessonPlanSliceError(
                "MATERIAL_EVIDENCE_INVALID: evidence references must be unique"
            )


@dataclass(frozen=True, slots=True)
class ApprovedLessonPlanScope:
    project_id: UUID
    lesson_unit_id: UUID
    lesson_key: str
    title: str
    scope_summary: str
    objective_summary: str
    duration_minutes: int
    approved_division_version_id: UUID
    material: ApprovedMaterialEvidence
    teacher_preferences: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.lesson_key.strip() or not self.title.strip():
            raise LessonPlanSliceError("LESSON_SCOPE_INVALID: lesson key and title are required")
        if not self.scope_summary.strip() or not self.objective_summary.strip():
            raise LessonPlanSliceError("LESSON_SCOPE_INVALID: approved lesson facts are required")
        if self.duration_minutes <= 0:
            raise LessonPlanSliceError("LESSON_SCOPE_INVALID: duration must be positive")

    def with_material(self, material: ApprovedMaterialEvidence) -> ApprovedLessonPlanScope:
        return replace(self, material=material)


@dataclass(frozen=True, slots=True)
class LessonPlanDefinition:
    id: UUID
    schema_json: dict[str, Any]


class LessonPlanDraftArtifactPort(Protocol):
    def create(
        self,
        project_id: UUID,
        *,
        artifact_key: str,
        artifact_type: str,
        branch_key: str,
        content_definition_version_id: UUID,
        draft_branch: str,
        initial_content: dict[str, Any],
        request_id: str | None,
        lesson_unit_id: UUID | None = None,
    ) -> object: ...


class LessonPlanGenerator(Protocol):
    def generate(self, scope: ApprovedLessonPlanScope) -> dict[str, Any]: ...


class DeterministicLessonPlanFake:
    """A scripted test generator that never invokes a model provider."""

    def __init__(self, content: dict[str, Any]) -> None:
        self._content = copy.deepcopy(content)

    def generate(self, scope: ApprovedLessonPlanScope) -> dict[str, Any]:
        del scope
        return copy.deepcopy(self._content)


class LessonPlanSliceService:
    def __init__(
        self,
        *,
        definition: LessonPlanDefinition,
        artifact_port: LessonPlanDraftArtifactPort,
        generator: LessonPlanGenerator,
    ) -> None:
        self._definition = definition
        self._artifact_port = artifact_port
        self._generator = generator

    def generate(self, scope: ApprovedLessonPlanScope) -> object:
        self._validate_scope(scope)
        content = self._generator.generate(scope)
        LessonPlanBusinessValidator(self._definition).validate(scope, content)
        return self._artifact_port.create(
            scope.project_id,
            artifact_key=f"lesson-plan:{scope.lesson_key}",
            artifact_type="lesson_plan",
            branch_key="lesson_plan",
            content_definition_version_id=self._definition.id,
            draft_branch="generated",
            initial_content=content,
            request_id=None,
            lesson_unit_id=scope.lesson_unit_id,
        )

    @staticmethod
    def _validate_scope(scope: ApprovedLessonPlanScope) -> None:
        if scope.material.project_id != scope.project_id:
            raise LessonPlanSliceError(
                "MATERIAL_SCOPE_MISMATCH: material evidence belongs to another project"
            )


class LessonPlanBusinessValidator:
    def __init__(self, definition: LessonPlanDefinition) -> None:
        self._definition = definition

    def validate(self, scope: ApprovedLessonPlanScope, content: dict[str, Any]) -> None:
        section_keys = self._section_keys()
        if set(content) != set(section_keys):
            raise LessonPlanSliceError(
                "LESSON_PLAN_SECTION_MISMATCH: content differs from definition"
            )
        self._validate_schema(content)
        teaching_content = self._mapping(content, "teaching_content")
        self._validate_teaching_content(scope, teaching_content)
        objective_keys = self._validate_objectives(scope, content)
        self._validate_process(scope, content, objective_keys)

    def _section_keys(self) -> tuple[str, ...]:
        raw_properties = self._definition.schema_json.get("properties")
        if not isinstance(raw_properties, dict):
            raise LessonPlanSliceError(
                "LESSON_PLAN_DEFINITION_INVALID: published definition must declare twelve sections"
            )
        properties = cast(dict[str, Any], raw_properties)
        if len(properties) != 12:
            raise LessonPlanSliceError(
                "LESSON_PLAN_DEFINITION_INVALID: published definition must declare twelve sections"
            )
        keys = tuple(properties)
        if not all(key.strip() for key in keys):
            raise LessonPlanSliceError("LESSON_PLAN_DEFINITION_INVALID: section keys are invalid")
        return keys

    def _validate_schema(self, content: dict[str, Any]) -> None:
        errors = list(
            Draft202012Validator(self._definition.schema_json).iter_errors(content)  # pyright: ignore[reportUnknownMemberType]
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
        if teaching_content.get("source_lesson_unit_key") != scope.lesson_key:
            raise LessonPlanSliceError(
                "LESSON_SCOPE_MISMATCH: generated content targets another lesson"
            )
        if teaching_content.get("duration_minutes") != scope.duration_minutes:
            raise LessonPlanSliceError(
                "LESSON_DURATION_MISMATCH: generated duration differs from lesson"
            )
        evidence_refs = self._strings(teaching_content.get("teaching_evidence_refs"))
        if not evidence_refs or not set(evidence_refs) <= set(scope.material.evidence_refs):
            raise LessonPlanSliceError(
                "MATERIAL_SCOPE_MISMATCH: generated content cites unavailable material evidence"
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
    ) -> set[str]:
        raw_objectives = content.get("teaching_objectives")
        if not isinstance(raw_objectives, list) or not raw_objectives:
            raise LessonPlanSliceError("OBJECTIVE_REFERENCE_INVALID: objectives are required")
        objectives = cast(list[object], raw_objectives)
        keys: set[str] = set()
        for objective in objectives:
            if not isinstance(objective, Mapping):
                raise LessonPlanSliceError(
                    "OBJECTIVE_REFERENCE_INVALID: objective shape is invalid"
                )
            objective = cast(Mapping[str, Any], objective)
            key = objective.get("objective_key")
            evidence_refs = self._strings(objective.get("objective_evidence_refs"))
            if not isinstance(key, str) or not key.strip() or key in keys:
                raise LessonPlanSliceError(
                    "OBJECTIVE_REFERENCE_INVALID: objective keys must be unique"
                )
            if not evidence_refs or not set(evidence_refs) <= set(scope.material.evidence_refs):
                raise LessonPlanSliceError(
                    "OBJECTIVE_REFERENCE_INVALID: objective evidence is outside material scope"
                )
            keys.add(key)
        return keys

    def _validate_process(
        self,
        scope: ApprovedLessonPlanScope,
        content: Mapping[str, Any],
        objective_keys: set[str],
    ) -> None:
        raw_process = content.get("teaching_process")
        if not isinstance(raw_process, list) or not raw_process:
            raise LessonPlanSliceError("PROCESS_REFERENCE_INVALID: teaching process is required")
        process = cast(list[object], raw_process)
        total_minutes = 0
        for step in process:
            if not isinstance(step, Mapping):
                raise LessonPlanSliceError("PROCESS_REFERENCE_INVALID: process step is invalid")
            step = cast(Mapping[str, Any], step)
            minutes = step.get("process_minutes")
            keys = self._strings(step.get("process_objective_keys"))
            if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 0:
                raise LessonPlanSliceError("PROCESS_DURATION_MISMATCH: process minutes are invalid")
            if not keys or not set(keys) <= objective_keys:
                raise LessonPlanSliceError(
                    "PROCESS_REFERENCE_INVALID: process references an unknown objective"
                )
            total_minutes += minutes
        if total_minutes != scope.duration_minutes:
            raise LessonPlanSliceError(
                "PROCESS_DURATION_MISMATCH: process duration differs from lesson duration"
            )

    @staticmethod
    def _mapping(content: Mapping[str, Any], key: str) -> Mapping[str, Any]:
        value = content.get(key)
        if not isinstance(value, Mapping):
            raise LessonPlanSliceError(f"LESSON_PLAN_SECTION_MISMATCH: {key} is invalid")
        return cast(Mapping[str, Any], value)

    @staticmethod
    def _strings(value: object) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        items = cast(list[object], value)
        if any(not isinstance(item, str) for item in items):
            return ()
        return tuple(cast(str, item) for item in items)
