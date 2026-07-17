from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch"})


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def load_openapi() -> dict[str, Any]:
    value = yaml.safe_load((CONTRACTS / "api-surface.openapi.yaml").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def resolve_local(document: dict[str, Any], value: Any) -> Any:
    if not isinstance(value, dict) or set(value) != {"$ref"}:
        return value
    reference = value["$ref"]
    if not isinstance(reference, str) or not reference.startswith("#/"):
        return value
    resolved: Any = document
    for token in reference[2:].split("/"):
        resolved = resolved[token.replace("~1", "/").replace("~0", "~")]
    return resolved


def operations_by_id(openapi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for path_item in openapi["paths"].values():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation["operationId"]
            assert operation_id not in operations, f"duplicate operationId: {operation_id}"
            operations[operation_id] = operation
    return operations


def response_schema(
    openapi: dict[str, Any],
    operation: dict[str, Any],
    status: str,
    media_type: str,
) -> dict[str, Any]:
    response = resolve_local(openapi, operation["responses"][status])
    schema = response["content"][media_type]["schema"]
    if isinstance(schema, dict) and isinstance(schema.get("$ref"), str):
        reference = schema["$ref"]
        if reference.startswith("./"):
            return load_json(CONTRACTS / reference[2:])
    wrapped = deepcopy(schema)
    wrapped["components"] = deepcopy(openapi["components"])
    return wrapped


def validate(instance: dict[str, Any], schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


def test_mock_registry_and_all_stage0_fixtures_match_contracts() -> None:
    registry = load_json(CONTRACTS / "mock-scenarios.json")
    validate(registry, load_json(CONTRACTS / "mock-scenarios.schema.json"))
    openapi = load_openapi()
    operations = operations_by_id(openapi)

    scenario_ids: set[str] = set()
    for scenario in registry["stage0_contract_scenarios"]:
        assert scenario["id"] not in scenario_ids
        scenario_ids.add(scenario["id"])
        fixture_path = (CONTRACTS / scenario["fixture"]).resolve()
        assert fixture_path.is_relative_to(CONTRACTS.resolve())
        fixture = load_json(fixture_path)
        if "operation_id" in scenario:
            operation = operations[scenario["operation_id"]]
            schema = response_schema(
                openapi,
                operation,
                scenario["response_status"],
                scenario["media_type"],
            )
        else:
            schema = load_json(CONTRACTS / scenario["schema_file"])
        validate(fixture, schema)


def test_stage0_operations_preserve_idempotency_and_replay_headers() -> None:
    openapi = load_openapi()
    operations = operations_by_id(openapi)
    idempotent_operations = {
        "createProject",
        "createMaterialUploadSession",
        "confirmMaterialUpload",
        "cancelGenerationJob",
        "updateProjectLessons",
        "updateLessonBranches",
    }
    for operation_id in idempotent_operations:
        parameters = [
            resolve_local(openapi, item) for item in operations[operation_id]["parameters"]
        ]
        assert any(parameter.get("name") == "Idempotency-Key" for parameter in parameters)

    for operation_id in ("streamProjectEvents", "streamGenerationJobEvents"):
        parameters = [
            resolve_local(openapi, item) for item in operations[operation_id]["parameters"]
        ]
        assert any(parameter.get("name") == "Last-Event-ID" for parameter in parameters)

    for operation_id in ("updateProjectLessons", "updateLessonBranches"):
        parameters = [
            resolve_local(openapi, item) for item in operations[operation_id]["parameters"]
        ]
        assert any(parameter.get("name") == "If-Match" for parameter in parameters)


def test_health_operations_use_api_base_and_are_unauthenticated() -> None:
    operations = operations_by_id(load_openapi())

    for operation_id in ("getLiveness", "getReadiness"):
        operation = operations[operation_id]
        assert operation["security"] == []
        assert "servers" not in operation


def test_protected_operations_use_cookie_auth_without_identity_headers() -> None:
    openapi = load_openapi()
    assert openapi["security"] == [{"cookieAuth": []}]
    scheme = openapi["components"]["securitySchemes"]["cookieAuth"]
    assert scheme["type"] == "apiKey"
    assert scheme["in"] == "cookie"
    assert scheme["name"] == "shanhai_session"
    assert "identity headers" in scheme["description"]

    forbidden_headers = {"x-organization-id", "x-user-id", "x-principal-id"}
    for operation in operations_by_id(openapi).values():
        parameters = [resolve_local(openapi, item) for item in operation.get("parameters", [])]
        assert forbidden_headers.isdisjoint(
            str(parameter.get("name", "")).lower() for parameter in parameters
        )


def test_generated_types_and_shared_client_are_present() -> None:
    generated = CONTRACTS / "generated/typescript/schema.ts"
    client = CONTRACTS / "typescript/client.ts"

    assert "export interface paths" in generated.read_text(encoding="utf-8")
    assert "createClient<paths>" in client.read_text(encoding="utf-8")
