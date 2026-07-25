from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tests.contract.test_api_surface_partition import operations_by_id
from tests.contract.test_stage0_contracts import resolve_local

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_CONTRACT = ROOT / "contracts/api-surface.openapi.yaml"
PLANNED_CONTRACT = ROOT / "contracts/planned-api-surface.openapi.yaml"
GENERATED_TYPES = ROOT / "contracts/generated/typescript/schema.ts"

LESSON_PLAN_RESCUE_OPERATIONS = {
    (
        "get",
        "/projects/{project_id}/lessons/{lesson_id}/lesson-plan/artifact",
    ): "getLessonPlanArtifact",
    (
        "get",
        "/projects/{project_id}/lessons/{lesson_id}/lesson-plan/generation-jobs",
    ): "listLessonPlanGenerationJobs",
    (
        "post",
        "/lessons/{lesson_id}/lesson-plan/node-runs",
    ): "prepareLessonPlanGeneration",
    ("post", "/node-runs/{node_run_id}/start"): "startNodeRun",
    (
        "post",
        "/lessons/{lesson_id}/lesson-plan/artifact-versions/"
        "{artifact_version_id}/quality-validations",
    ): "startLessonPlanQualityValidation",
}

FORBIDDEN_PROJECT_QUERY_OPERATIONS = {
    "listProjectMaterials",
    "listProjectArtifacts",
    "listProjectGenerationJobs",
}


def _load(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _operation(document: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    operation = document["paths"][path][method]
    assert isinstance(operation, dict)
    return operation


def _parameter_names(document: dict[str, Any], operation: dict[str, Any]) -> set[str]:
    return {
        str(resolve_local(document, parameter)["name"])
        for parameter in operation.get("parameters", [])
    }


def test_lesson_plan_rescue_operations_are_active_only_and_generated() -> None:
    active = _load(ACTIVE_CONTRACT)
    planned = _load(PLANNED_CONTRACT)
    generated = GENERATED_TYPES.read_text(encoding="utf-8")
    planned_operation_ids = set(operations_by_id(planned))

    for (method, path), operation_id in LESSON_PLAN_RESCUE_OPERATIONS.items():
        assert _operation(active, method, path)["operationId"] == operation_id
        assert operation_id not in planned_operation_ids
        assert f"    {operation_id}:" in generated


def test_lesson_plan_recovery_queries_are_exact_lesson_scoped() -> None:
    active = _load(ACTIVE_CONTRACT)

    for method, path in tuple(LESSON_PLAN_RESCUE_OPERATIONS)[:2]:
        operation = _operation(active, method, path)
        assert _parameter_names(active, operation) == {"project_id", "lesson_id"}


def test_project_level_query_platform_is_not_part_of_the_rescue_slice() -> None:
    active_operation_ids = set(operations_by_id(_load(ACTIVE_CONTRACT)))

    assert active_operation_ids.isdisjoint(FORBIDDEN_PROJECT_QUERY_OPERATIONS)
