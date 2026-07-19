#!/usr/bin/env python3
"""Require the current OpenAPI surface to match registered runtime operations."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from apps.api.main import create_app
from apps.api.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
CURRENT_CONTRACT = ROOT / "contracts/api-surface.openapi.yaml"
PLANNED_CONTRACT = ROOT / "contracts/planned-api-surface.openapi.yaml"
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})


def load_yaml(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"OpenAPI document must be an object: {path.name}")
    return document


def _operations(
    document: Mapping[str, Any],
    label: str,
    errors: list[str],
) -> dict[str, Mapping[str, Any]]:
    operations: dict[str, Mapping[str, Any]] = {}
    paths = document.get("paths", {})
    if not isinstance(paths, Mapping):
        errors.append(f"{label} paths must be an object")
        return operations
    for path_item in paths.values():
        if not isinstance(path_item, Mapping):
            continue
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, Mapping):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                errors.append(f"{label} operation lacks operationId")
                continue
            if operation_id in operations:
                errors.append(f"{label} has duplicate operationId: {operation_id}")
                continue
            operations[operation_id] = operation
    return operations


def find_surface_errors(
    runtime: Mapping[str, Any],
    current: Mapping[str, Any],
    planned: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if current.get("x-shanhai-contract-kind") != "runtime":
        errors.append("current contract kind must be runtime")
    if planned.get("x-shanhai-contract-kind") != "planned":
        errors.append("planned contract kind must be planned")

    runtime_operations = _operations(runtime, "runtime", errors)
    current_operations = _operations(current, "current contract", errors)
    planned_operations = _operations(planned, "planned contract", errors)

    for operation_id in sorted(set(current_operations) - set(runtime_operations)):
        errors.append(f"current contract operation is not registered at runtime: {operation_id}")
    for operation_id in sorted(set(runtime_operations) - set(current_operations)):
        errors.append(f"runtime operation is missing from current contract: {operation_id}")
    for operation_id in sorted(set(current_operations) & set(planned_operations)):
        errors.append(f"operation appears in current and planned contracts: {operation_id}")
    for operation_id, operation in sorted(planned_operations.items()):
        if operation.get("x-shanhai-availability") != "planned":
            errors.append(f"planned operation lacks availability marker: {operation_id}")

    return sorted(set(errors))


def main() -> int:
    try:
        current = load_yaml(CURRENT_CONTRACT)
        planned = load_yaml(PLANNED_CONTRACT)
        runtime = create_app(settings=Settings(_env_file=None, environment="test")).openapi()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"cannot load API surfaces: {type(exc).__name__}", file=sys.stderr)
        return 2

    errors = find_surface_errors(runtime, current, planned)
    if errors:
        for error in errors:
            print(f"API surface mismatch: {error}", file=sys.stderr)
        return 1
    print("current OpenAPI operations exactly match the runtime surface")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
