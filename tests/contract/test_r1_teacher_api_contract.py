from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tests.contract.test_stage0_contracts import resolve_local

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_CONTRACT = ROOT / "contracts/api-surface.openapi.yaml"
PLANNED_CONTRACT = ROOT / "contracts/planned-api-surface.openapi.yaml"
GENERATED_TYPES = ROOT / "contracts/generated/typescript/schema.ts"

R1_QUERY_OPERATIONS = {
    ("get", "/projects/{project_id}/materials"): "listProjectMaterials",
    ("get", "/projects/{project_id}/artifacts"): "listProjectArtifacts",
    ("get", "/projects/{project_id}/generation-jobs"): "listProjectGenerationJobs",
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


def test_r1_query_operations_are_active_only_and_generated() -> None:
    active = _load(ACTIVE_CONTRACT)
    planned = _load(PLANNED_CONTRACT)
    generated = GENERATED_TYPES.read_text(encoding="utf-8")

    for (method, path), operation_id in R1_QUERY_OPERATIONS.items():
        assert _operation(active, method, path)["operationId"] == operation_id
        assert all(
            item.get("operationId") != operation_id
            for path_item in planned["paths"].values()
            for item in path_item.values()
            if isinstance(item, dict)
        )
        assert f"    {operation_id}:" in generated


def test_r1_query_operations_use_exact_filters_and_cursor_pagination() -> None:
    active = _load(ACTIVE_CONTRACT)
    expected = {
        "/projects/{project_id}/materials": set(),
        "/projects/{project_id}/artifacts": {"lesson_id", "artifact_type"},
        "/projects/{project_id}/generation-jobs": set(),
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


def test_r1_query_envelopes_are_explicit_schemas() -> None:
    active = _load(ACTIVE_CONTRACT)

    for name in (
        "SourceMaterialListEnvelope",
        "ArtifactListEnvelope",
        "GenerationJobListEnvelope",
    ):
        assert name in active["components"]["schemas"]
