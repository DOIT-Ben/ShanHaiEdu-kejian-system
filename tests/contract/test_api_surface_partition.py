from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from apps.api.main import create_app
from apps.api.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
CURRENT_CONTRACT = ROOT / "contracts/api-surface.openapi.yaml"
PLANNED_CONTRACT = ROOT / "contracts/planned-api-surface.openapi.yaml"
GENERATED_TYPES = ROOT / "contracts/generated/typescript/schema.ts"
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})
INITIAL_PLANNED_OPERATIONS = {
    "createCreationPackage",
    "startNodeRun",
    "updateProject",
}
PROMOTED_INTRO_OPERATIONS = {
    "getLessonIntroOptions",
    "selectLessonIntroOption",
}


def load_yaml(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def operations_by_id(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for path_item in document["paths"].values():
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation["operationId"]
            assert operation_id not in operations
            operations[operation_id] = operation
    return operations


def test_current_contract_exactly_matches_runtime_operations() -> None:
    current = load_yaml(CURRENT_CONTRACT)
    runtime = create_app(settings=Settings(_env_file=None, environment="test")).openapi()

    assert current["x-shanhai-contract-kind"] == "runtime"
    assert set(operations_by_id(current)) == set(operations_by_id(runtime))


def test_planned_operations_are_separate_and_explicitly_marked() -> None:
    current_operations = operations_by_id(load_yaml(CURRENT_CONTRACT))
    planned = load_yaml(PLANNED_CONTRACT)
    planned_operations = operations_by_id(planned)

    assert planned["x-shanhai-contract-kind"] == "planned"
    assert set(planned_operations) == INITIAL_PLANNED_OPERATIONS
    assert set(current_operations).isdisjoint(planned_operations)
    assert all(
        operation["x-shanhai-availability"] == "planned"
        for operation in planned_operations.values()
    )


def test_generated_frontend_types_exclude_planned_operations() -> None:
    generated = GENERATED_TYPES.read_text(encoding="utf-8")

    for operation_id in INITIAL_PLANNED_OPERATIONS:
        assert f'operations["{operation_id}"]' not in generated
        assert f"    {operation_id}:" not in generated


def test_intro_operations_are_runtime_only_and_generated() -> None:
    current_operations = operations_by_id(load_yaml(CURRENT_CONTRACT))
    planned_operations = operations_by_id(load_yaml(PLANNED_CONTRACT))
    generated = GENERATED_TYPES.read_text(encoding="utf-8")

    assert PROMOTED_INTRO_OPERATIONS.issubset(current_operations)
    assert PROMOTED_INTRO_OPERATIONS.isdisjoint(planned_operations)
    for operation_id in PROMOTED_INTRO_OPERATIONS:
        assert f"    {operation_id}:" in generated
