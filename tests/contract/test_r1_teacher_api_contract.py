from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tests.contract.test_stage0_contracts import resolve_local

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_CONTRACT = ROOT / "contracts/api-surface.openapi.yaml"
PLANNED_CONTRACT = ROOT / "contracts/planned-api-surface.openapi.yaml"
GENERATED_TYPES = ROOT / "contracts/generated/typescript/schema.ts"

R1_OPERATIONS = {
    ("get", "/projects/{project_id}/materials"): "listProjectMaterials",
    ("get", "/projects/{project_id}/artifacts"): "listProjectArtifacts",
    ("get", "/projects/{project_id}/generation-jobs"): "listProjectGenerationJobs",
    ("post", "/projects/{project_id}/material-scope/versions"): ("createMaterialScopeVersion"),
    ("post", "/projects/{project_id}/lesson-division/node-runs"): ("prepareLessonDivision"),
    ("post", "/lessons/{lesson_id}/lesson-plan/node-runs"): ("prepareLessonPlanGeneration"),
    ("post", "/lessons/{lesson_id}/intro-options/node-runs"): ("prepareIntroOptionGeneration"),
    ("post", "/node-runs/{node_run_id}/start"): "startNodeRun",
    ("post", "/artifact-versions/{artifact_version_id}/quality-validations"): (
        "startArtifactVersionQualityValidation"
    ),
}


def _load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _operation(document: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    operation = document["paths"][path][method]
    assert isinstance(operation, dict)
    return operation


def _parameter_names(document: dict[str, Any], operation: dict[str, Any]) -> set[str]:
    return {
        str(resolve_local(document, parameter)["name"])
        for parameter in operation.get("parameters", [])
    }


def _request_schema(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    resolved = resolve_local(document, schema)
    assert isinstance(resolved, dict)
    return resolved


def test_r1_operations_are_active_only_and_generated() -> None:
    active = _load(ACTIVE_CONTRACT)
    planned = _load(PLANNED_CONTRACT)
    generated = GENERATED_TYPES.read_text(encoding="utf-8")

    for (method, path), operation_id in R1_OPERATIONS.items():
        assert _operation(active, method, path)["operationId"] == operation_id
        assert all(
            item.get("operationId") != operation_id
            for path_item in planned["paths"].values()
            for item in path_item.values()
            if isinstance(item, dict)
        )
        assert f"    {operation_id}:" in generated


def test_r1_list_operations_use_exact_filters_and_cursor_pagination() -> None:
    active = _load(ACTIVE_CONTRACT)
    expected = {
        "/projects/{project_id}/materials": set(),
        "/projects/{project_id}/artifacts": {"lesson_id", "artifact_type"},
        "/projects/{project_id}/generation-jobs": {"lesson_id"},
    }

    for path, filters in expected.items():
        operation = _operation(active, "get", path)
        names = _parameter_names(active, operation)
        assert names == {"project_id", "page[cursor]", "page[limit]", *filters}
        response = resolve_local(active, operation["responses"]["200"])
        schema = resolve_local(
            active,
            response["content"]["application/json"]["schema"],
        )
        meta = resolve_local(active, schema["properties"]["meta"])
        assert "next_cursor" in meta["required"]


def test_r1_commands_have_narrow_payloads_and_idempotency() -> None:
    active = _load(ACTIVE_CONTRACT)
    write_operations = {
        operation_id: _operation(active, method, path)
        for (method, path), operation_id in R1_OPERATIONS.items()
        if method == "post"
    }
    for operation in write_operations.values():
        assert "Idempotency-Key" in _parameter_names(active, operation)
        assert operation["security"] == [{"BrowserOrigin": [], "CsrfToken": [], "cookieAuth": []}]

    scope = _request_schema(active, write_operations["createMaterialScopeVersion"])
    assert scope["additionalProperties"] is False
    assert set(scope["required"]) == {
        "source_material_id",
        "material_parse_version_id",
        "page_start",
        "page_end",
    }
    assert set(scope["properties"]) == set(scope["required"])

    division = _request_schema(active, write_operations["prepareLessonDivision"])
    assert division["additionalProperties"] is False
    assert division["required"] == ["material_scope_artifact_version_id"]
    assert set(division["properties"]) == {"material_scope_artifact_version_id"}

    lesson_plan = write_operations["prepareLessonPlanGeneration"]
    assert "requestBody" not in lesson_plan

    intro = _request_schema(active, write_operations["prepareIntroOptionGeneration"])
    assert intro["additionalProperties"] is False
    assert intro["required"] == ["generation_mode"]
    assert set(intro["properties"]) == {
        "generation_mode",
        "source_artifact_version_id",
    }

    start = _request_schema(active, write_operations["startNodeRun"])
    assert start["additionalProperties"] is False
    assert set(start["properties"]) == {"user_revision"}
    assert start["properties"]["user_revision"]["maxLength"] == 6000

    quality = write_operations["startArtifactVersionQualityValidation"]
    assert "requestBody" not in quality
    assert set(quality["responses"]) >= {"202", "4XX"}


def test_r1_job_and_acceptance_schemas_expose_exact_persisted_links() -> None:
    active = _load(ACTIVE_CONTRACT)
    schemas = active["components"]["schemas"]
    job = schemas["GenerationJob"]

    assert {
        "node_run_id",
        "lesson_unit_id",
        "result_artifact_version_id",
    } <= set(job["properties"])
    for name in (
        "SourceMaterialListEnvelope",
        "ArtifactListEnvelope",
        "GenerationJobListEnvelope",
        "NodeRunEnvelope",
        "AcceptedNodeRunEnvelope",
    ):
        assert name in schemas

    accepted = schemas["AcceptedNodeRunEnvelope"]
    data = resolve_local(active, accepted["properties"]["data"])
    assert set(data["required"]) == {"node_run_id", "status", "events_url"}
