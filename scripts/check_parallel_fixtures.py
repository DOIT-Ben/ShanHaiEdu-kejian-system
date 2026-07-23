#!/usr/bin/env python3
"""Validate UUID identities and deterministic parallel-input projections."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "contracts/fixtures/contract-freeze/primary-math-two-lessons.json"
MAINLINE_EXAMPLE_PATH = ROOT / "contracts/fixtures/parallel-inputs/mainline/example.json"
PPT_EXAMPLE_PATH = ROOT / "contracts/fixtures/parallel-inputs/ppt/example.json"
VIDEO_EXAMPLE_PATH = ROOT / "contracts/fixtures/parallel-inputs/video/example.json"

PROJECT_UUID_FIELDS = (
    "organization_id",
    "project_id",
    "content_release_id",
    "workflow_definition_version_id",
    "source_material_id",
    "material_parse_version_id",
    "material_scope_artifact_version_id",
    "lesson_division_artifact_version_id",
    "lesson_division_approval_id",
)
EXPECTED_LESSON_PLAN_SECTIONS = (
    "teaching_content",
    "material_analysis",
    "learner_analysis",
    "design_intent",
    "teaching_objectives",
    "key_difficulties_and_strategies",
    "preparation",
    "teaching_process",
    "board_design",
    "lesson_summary",
    "differentiated_homework",
    "teaching_reflection",
)
VIDEO_FORBIDDEN_FIELDS = {
    "approved_lesson_plan_version_id",
    "lesson_plan_content_hash",
    "material_parse_version_id",
    "material_scope_artifact_version_id",
    "ppt_outline_version_id",
    "ppt_page_specs_version_id",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _require_uuid(errors: list[str], label: str, value: object) -> None:
    if not _is_uuid(value):
        errors.append(f"{label} must be a canonical UUID")


def _require_hash(errors: list[str], label: str, value: object) -> None:
    if not _is_sha256(value):
        errors.append(f"{label} must be a 64-character hexadecimal SHA-256")


def validate_parallel_fixture(root: Path = ROOT) -> list[str]:
    fixture = _load(root / FIXTURE_PATH.relative_to(ROOT))
    mainline_example = _load(root / MAINLINE_EXAMPLE_PATH.relative_to(ROOT))
    ppt_example = _load(root / PPT_EXAMPLE_PATH.relative_to(ROOT))
    video_example = _load(root / VIDEO_EXAMPLE_PATH.relative_to(ROOT))
    errors: list[str] = []

    project = fixture.get("project", {})
    for field in PROJECT_UUID_FIELDS:
        _require_uuid(errors, f"project.{field}", project.get(field))
    _require_hash(errors, "project.material_evidence_hash", project.get("material_evidence_hash"))

    lessons = fixture.get("lessons", [])
    lesson_by_id: dict[str, dict[str, Any]] = {}
    plan_versions: set[str] = set()
    intro_versions: set[str] = set()
    selections: set[str] = set()
    for index, lesson in enumerate(lessons):
        prefix = f"lessons[{index}]"
        lesson_id = lesson.get("lesson_id")
        _require_uuid(errors, f"{prefix}.lesson_id", lesson_id)
        if isinstance(lesson_id, str):
            if lesson_id in lesson_by_id:
                errors.append(f"duplicate lesson_id: {lesson_id}")
            lesson_by_id[lesson_id] = lesson

        plan = lesson.get("lesson_plan", {})
        intro = lesson.get("intro", {})
        for field in ("artifact_id", "artifact_version_id", "approval_id"):
            _require_uuid(errors, f"{prefix}.lesson_plan.{field}", plan.get(field))
            _require_uuid(errors, f"{prefix}.intro.{field}", intro.get(field))
        _require_uuid(errors, f"{prefix}.intro.selection_id", intro.get("selection_id"))
        _require_hash(errors, f"{prefix}.lesson_plan.content_hash", plan.get("content_hash"))
        _require_hash(errors, f"{prefix}.intro.content_hash", intro.get("content_hash"))

        if tuple(plan.get("sections", [])) != EXPECTED_LESSON_PLAN_SECTIONS:
            errors.append(f"{prefix}.lesson_plan.sections must be the frozen twelve-part order")
        if plan.get("approval_status") != "approved":
            errors.append(f"{prefix}.lesson_plan must be approved")
        if intro.get("approval_status") != "approved":
            errors.append(f"{prefix}.intro must be approved")

        plan_version = plan.get("artifact_version_id")
        intro_version = intro.get("artifact_version_id")
        selection_id = intro.get("selection_id")
        for label, value, seen in (
            ("lesson-plan version", plan_version, plan_versions),
            ("intro option-set version", intro_version, intro_versions),
            ("IntroSelection", selection_id, selections),
        ):
            if isinstance(value, str):
                if value in seen:
                    errors.append(f"duplicate {label}: {value}")
                seen.add(value)

        ppt_input = lesson.get("parallel_inputs", {}).get("ppt", {})
        video_input = lesson.get("parallel_inputs", {}).get("video", {})
        expected_project_id = project.get("project_id")
        if (
            ppt_input.get("project_id") != expected_project_id
            or ppt_input.get("lesson_id") != lesson_id
        ):
            errors.append(f"{prefix}.parallel_inputs.ppt scope does not match its owner lesson")
        if ppt_input.get("approved_lesson_plan_version_id") != plan_version:
            errors.append(f"{prefix}.parallel_inputs.ppt does not use the owner lesson plan")
        if (
            video_input.get("project_id") != expected_project_id
            or video_input.get("lesson_id") != lesson_id
        ):
            errors.append(f"{prefix}.parallel_inputs.video scope does not match its owner lesson")
        if video_input.get("intro_selection_id") != selection_id:
            errors.append(f"{prefix}.parallel_inputs.video does not use the owner IntroSelection")
        if video_input.get("intro_option_set_version_id") != intro_version:
            errors.append(
                f"{prefix}.parallel_inputs.video does not use the owner option-set version"
            )
        _require_hash(
            errors,
            f"{prefix}.parallel_inputs.video.selected_option_snapshot_hash",
            video_input.get("selected_option_snapshot_hash"),
        )
        leaked_fields = VIDEO_FORBIDDEN_FIELDS.intersection(video_input)
        if leaked_fields:
            errors.append(
                f"{prefix}.parallel_inputs.video leaks forbidden fields: {sorted(leaked_fields)}"
            )

    _check_mainline_projection(errors, lesson_by_id, mainline_example)
    _check_ppt_projection(errors, lesson_by_id, ppt_example)
    _check_video_projection(errors, lesson_by_id, video_example)
    return errors


def _check_mainline_projection(
    errors: list[str],
    lesson_by_id: dict[str, dict[str, Any]],
    example: dict[str, Any],
) -> None:
    handoffs = {item.get("lesson_id"): item for item in example.get("handoffs", [])}
    if set(handoffs) != set(lesson_by_id):
        errors.append("mainline example must contain exactly the public fixture lesson IDs")
        return
    for lesson_id, lesson in lesson_by_id.items():
        handoff = handoffs[lesson_id]
        if handoff.get("ppt_input") != lesson["lesson_plan"]["artifact_version_id"]:
            errors.append(f"mainline PPT handoff drifted for lesson {lesson_id}")
        if handoff.get("video_input") != lesson["intro"]["selection_id"]:
            errors.append(f"mainline video handoff drifted for lesson {lesson_id}")


def _check_ppt_projection(
    errors: list[str],
    lesson_by_id: dict[str, dict[str, Any]],
    example: dict[str, Any],
) -> None:
    inputs = {item.get("lesson_id"): item for item in example.get("inputs", [])}
    if set(inputs) != set(lesson_by_id):
        errors.append("PPT example must contain exactly the public fixture lesson IDs")
        return
    for lesson_id, lesson in lesson_by_id.items():
        expected = lesson["parallel_inputs"]["ppt"]
        actual = inputs[lesson_id]
        for field in (
            "project_id",
            "lesson_id",
            "approved_lesson_plan_version_id",
            "material_parse_version_id",
            "material_scope_artifact_version_id",
        ):
            if actual.get(field) != expected.get(field):
                errors.append(f"PPT example field {field} drifted for lesson {lesson_id}")


def _check_video_projection(
    errors: list[str],
    lesson_by_id: dict[str, dict[str, Any]],
    example: dict[str, Any],
) -> None:
    inputs = {item.get("lesson_id"): item for item in example.get("inputs", [])}
    if set(inputs) != set(lesson_by_id):
        errors.append("video example must contain exactly the public fixture lesson IDs")
        return
    if set(example.get("forbidden_fields", [])) != VIDEO_FORBIDDEN_FIELDS:
        errors.append("video example forbidden_fields drifted from the frozen context boundary")
    for lesson_id, lesson in lesson_by_id.items():
        expected = lesson["parallel_inputs"]["video"]
        actual = inputs[lesson_id]
        for field in (
            "project_id",
            "lesson_id",
            "intro_selection_id",
            "intro_option_set_version_id",
            "selected_option_key",
        ):
            if actual.get(field) != expected.get(field):
                errors.append(f"video example field {field} drifted for lesson {lesson_id}")
        leaked_fields = VIDEO_FORBIDDEN_FIELDS.intersection(actual)
        if leaked_fields:
            errors.append(f"video example leaks forbidden fields for lesson {lesson_id}")


def main() -> int:
    errors = validate_parallel_fixture()
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("parallel fixture identity and projection checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
