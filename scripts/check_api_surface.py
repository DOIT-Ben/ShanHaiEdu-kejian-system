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
) -> dict[str, tuple[str, str, Mapping[str, Any]]]:
    operations: dict[str, tuple[str, str, Mapping[str, Any]]] = {}
    paths = document.get("paths", {})
    if not isinstance(paths, Mapping):
        errors.append(f"{label} paths must be an object")
        return operations
    path_prefix = _relative_server_prefix(document)
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, Mapping):
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
            effective_path = f"{path_prefix}{path}" if path_prefix else path
            operations[operation_id] = (effective_path, method, operation)
    return operations


def _relative_server_prefix(document: Mapping[str, Any]) -> str:
    servers = document.get("servers")
    if not isinstance(servers, list) or len(servers) != 1:
        return ""
    server = servers[0]
    if not isinstance(server, Mapping):
        return ""
    url = server.get("url")
    if not isinstance(url, str) or not url.startswith("/"):
        return ""
    return url.rstrip("/")


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
    for operation_id in sorted(set(runtime_operations) & set(current_operations)):
        runtime_path, runtime_method, _runtime_operation = runtime_operations[operation_id]
        current_path, current_method, _current_operation = current_operations[operation_id]
        if (runtime_path, runtime_method) != (current_path, current_method):
            errors.append(
                "current contract path/method differs from runtime: "
                f"{operation_id} ({current_method.upper()} {current_path} != "
                f"{runtime_method.upper()} {runtime_path})"
            )
    for operation_id in sorted(set(current_operations) & set(planned_operations)):
        errors.append(f"operation appears in current and planned contracts: {operation_id}")
    for operation_id, (_path, _method, operation) in sorted(planned_operations.items()):
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
