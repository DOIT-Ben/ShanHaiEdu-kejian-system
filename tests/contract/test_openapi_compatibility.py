from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml

from scripts.check_openapi_compatibility import (
    find_breaking_changes,
    find_partition_aware_breaking_changes,
)

ROOT = Path(__file__).resolve().parents[2]


def load_current_contract() -> dict:
    document = yaml.safe_load(
        (ROOT / "contracts/api-surface.openapi.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(document, dict)
    return document


def test_current_contract_is_compatible_with_itself() -> None:
    contract = load_current_contract()

    assert find_breaking_changes(contract, deepcopy(contract)) == []


def test_removed_operation_is_breaking() -> None:
    base = load_current_contract()
    current = deepcopy(base)
    del current["paths"]["/projects"]["post"]

    errors = find_breaking_changes(base, current)

    assert "POST /projects: operation removed" in errors


def test_initial_mixed_surface_partition_tracks_never_runtime_contracts() -> None:
    base = load_current_contract()
    base.pop("x-shanhai-contract-kind")
    operation = {
        "operationId": "futureOperation",
        "responses": {"204": {"description": "Planned"}},
    }
    schema = {"type": "object", "properties": {"id": {"type": "string"}}}
    base["paths"]["/future"] = {"post": deepcopy(operation)}
    base["components"]["schemas"]["FutureEnvelope"] = deepcopy(schema)
    current = deepcopy(base)
    current["x-shanhai-contract-kind"] = "runtime"
    del current["paths"]["/future"]
    del current["components"]["schemas"]["FutureEnvelope"]
    planned = {
        "x-shanhai-contract-kind": "planned",
        "paths": {
            "/future": {
                "post": {
                    **deepcopy(operation),
                    "x-shanhai-availability": "planned",
                }
            }
        },
        "components": {"schemas": {"FutureEnvelope": deepcopy(schema)}},
    }

    assert find_partition_aware_breaking_changes(base, current, planned) == []

    planned["paths"]["/future"]["post"]["responses"]["204"]["description"] = (
        "Changed during partition"
    )
    errors = find_partition_aware_breaking_changes(base, current, planned)
    assert "POST /future: operation removed" in errors


def test_runtime_contract_cannot_later_move_back_to_planned() -> None:
    base = load_current_contract()
    operation = {
        "operationId": "futureOperation",
        "responses": {"204": {"description": "Planned"}},
    }
    base["paths"]["/future"] = {"post": deepcopy(operation)}
    current = deepcopy(base)
    del current["paths"]["/future"]
    planned = {
        "x-shanhai-contract-kind": "planned",
        "paths": {
            "/future": {
                "post": {
                    **deepcopy(operation),
                    "x-shanhai-availability": "planned",
                }
            }
        },
    }

    errors = find_partition_aware_breaking_changes(base, current, planned)

    assert "POST /future: operation removed" in errors


def test_required_property_and_changed_enum_values_are_breaking() -> None:
    base = load_current_contract()
    current = deepcopy(base)
    project = current["components"]["schemas"]["LegacyProject"]
    project["required"].append("grade")
    project["properties"]["status"]["enum"].remove("archived")

    errors = find_breaking_changes(base, current)

    assert "components.schemas.LegacyProject: required properties changed" in errors
    assert "components.schemas.LegacyProject.status: enum values changed" in errors


def test_path_parameter_removal_and_new_required_parameter_are_breaking() -> None:
    base = load_current_contract()
    project_path = base["paths"]["/projects/{project_id}"]
    project_path["parameters"] = [{"$ref": "#/components/parameters/ProjectId"}]
    for method in ("get",):
        project_path[method]["parameters"] = [
            parameter
            for parameter in project_path[method]["parameters"]
            if parameter.get("$ref") != "#/components/parameters/ProjectId"
        ]
    current = deepcopy(base)
    del current["paths"]["/projects/{project_id}"]["parameters"]
    current["paths"]["/projects/{project_id}"]["get"]["parameters"].append(
        {
            "name": "X-Required-Client",
            "in": "header",
            "required": True,
            "schema": {"type": "string"},
        }
    )

    errors = find_breaking_changes(base, current)

    assert "GET /projects/{project_id}: parameter removed: ('path', 'project_id')" in errors
    assert (
        "GET /projects/{project_id}: required parameter added: ('header', 'X-Required-Client')"
        in errors
    )


def test_request_and_response_schema_changes_are_breaking() -> None:
    base = load_current_contract()
    current = deepcopy(base)
    current["paths"]["/projects"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ] = {"type": "string"}
    current["paths"]["/projects"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ] = {"type": "string"}

    errors = find_breaking_changes(base, current)

    assert "POST /projects request body application/json: type changed" in errors
    assert "GET /projects response 200 application/json: type changed" in errors


def test_one_of_wrapper_is_compatible_when_legacy_branch_remains() -> None:
    base = load_current_contract()
    current = deepcopy(base)
    original = deepcopy(
        current["paths"]["/projects"]["post"]["requestBody"]["content"]["application/json"][
            "schema"
        ]
    )
    current["paths"]["/projects"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ] = {
        "oneOf": [
            original,
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "knowledge_point", "execution_mode"],
                "properties": {
                    "title": {"type": "string"},
                    "knowledge_point": {"type": "string"},
                    "execution_mode": {"enum": ["guided", "automatic"]},
                },
            },
        ]
    }

    assert find_breaking_changes(base, current) == []


def test_one_of_wrapper_is_breaking_when_legacy_branch_is_removed() -> None:
    base = load_current_contract()
    current = deepcopy(base)
    current["paths"]["/projects"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ] = {
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "knowledge_point", "execution_mode"],
                "properties": {
                    "title": {"type": "string"},
                    "knowledge_point": {"type": "string"},
                    "execution_mode": {"enum": ["guided", "automatic"]},
                },
            }
        ]
    }

    errors = find_breaking_changes(base, current)

    assert (
        "POST /projects request body application/json: no backward-compatible schema branch remains"
        in errors
    )
