from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str) -> dict[str, object]:
    return yaml.safe_load((ROOT / "contracts" / name).read_text(encoding="utf-8"))


def test_start_node_run_is_an_active_synchronous_runtime_command() -> None:
    active = _load("api-surface.openapi.yaml")
    planned = _load("planned-api-surface.openapi.yaml")

    path = "/node-runs/{node_run_id}/start"
    assert path not in planned["paths"]

    operation = active["paths"][path]["post"]
    assert operation["operationId"] == "startNodeRun"
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/StartNodeRunRequest"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/NodeExecutionEnvelope"
    }

    request_schema = active["components"]["schemas"]["StartNodeRunRequest"]
    assert request_schema["additionalProperties"] is False
    assert set(request_schema["properties"]) == {"user_revision"}

    result_schema = active["components"]["schemas"]["NodeExecutionResult"]
    assert set(result_schema["required"]) == {
        "node_run_id",
        "artifact_version_id",
        "creation_package_id",
        "attempt_id",
        "usage_id",
    }


def test_lesson_division_preparation_is_an_active_runtime_command() -> None:
    active = _load("api-surface.openapi.yaml")

    operation = active["paths"]["/projects/{project_id}/lesson-division-runs"]["post"]
    assert operation["operationId"] == "prepareLessonDivision"
    assert operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/LessonDivisionPreparationEnvelope"
    }
