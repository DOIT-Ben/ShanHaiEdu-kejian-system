#!/usr/bin/env python3
"""Reject high-confidence breaking changes to the shared OpenAPI contract."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("contracts/api-surface.openapi.yaml")
PLANNED_CONTRACT_PATH = Path("contracts/planned-api-surface.openapi.yaml")
BREAKING_TRANSITIONS_PATH = Path("contracts/openapi-breaking-transitions.json")
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
TRANSITION_FIELDS = frozenset(
    {
        "id",
        "issue",
        "reason",
        "base_contract_sha256",
        "current_contract_sha256",
        "breaking_errors_sha256",
        "breaking_errors",
    }
)


@dataclass(frozen=True)
class BreakingTransition:
    id: str
    issue: int
    reason: str
    base_contract_sha256: str
    current_contract_sha256: str
    breaking_errors_sha256: str
    breaking_errors: tuple[str, ...]


def contract_sha256(contract: bytes) -> str:
    return sha256(contract).hexdigest()


def normalize_breaking_errors(errors: list[str]) -> list[str]:
    return sorted(set(errors))


def errors_sha256(errors: list[str]) -> str:
    normalized = normalize_breaking_errors(errors)
    canonical = json.dumps(
        normalized,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def parse_breaking_transitions(document: Any) -> tuple[BreakingTransition, ...]:
    if not isinstance(document, dict) or set(document) != {"version", "transitions"}:
        raise ValueError("breaking transition registry must contain version and transitions")
    if document["version"] != 1 or not isinstance(document["transitions"], list):
        raise ValueError("unsupported breaking transition registry version")

    parsed: list[BreakingTransition] = []
    seen_ids: set[str] = set()
    for raw_transition in document["transitions"]:
        if not isinstance(raw_transition, dict) or set(raw_transition) != TRANSITION_FIELDS:
            raise ValueError("breaking transition contains missing or unknown fields")

        transition_id = raw_transition["id"]
        issue = raw_transition["issue"]
        reason = raw_transition["reason"]
        hashes = (
            raw_transition["base_contract_sha256"],
            raw_transition["current_contract_sha256"],
            raw_transition["breaking_errors_sha256"],
        )
        raw_errors = raw_transition["breaking_errors"]
        if (
            not isinstance(transition_id, str)
            or not transition_id
            or transition_id in seen_ids
            or not isinstance(issue, int)
            or isinstance(issue, bool)
            or issue <= 0
            or not isinstance(reason, str)
            or not reason.strip()
            or any(
                not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None
                for value in hashes
            )
            or not isinstance(raw_errors, list)
            or not raw_errors
            or any(not isinstance(error, str) or not error for error in raw_errors)
            or any("*" in error for error in raw_errors)
            or raw_errors != normalize_breaking_errors(raw_errors)
            or raw_transition["breaking_errors_sha256"] != errors_sha256(raw_errors)
        ):
            raise ValueError(f"invalid breaking transition record: {transition_id!r}")

        seen_ids.add(transition_id)
        parsed.append(
            BreakingTransition(
                id=transition_id,
                issue=issue,
                reason=reason,
                base_contract_sha256=raw_transition["base_contract_sha256"],
                current_contract_sha256=raw_transition["current_contract_sha256"],
                breaking_errors_sha256=raw_transition["breaking_errors_sha256"],
                breaking_errors=tuple(raw_errors),
            )
        )
    return tuple(parsed)


def find_approved_breaking_transition(
    base_contract: bytes,
    current_contract: bytes,
    errors: list[str],
    transitions: tuple[BreakingTransition, ...],
) -> BreakingTransition | None:
    normalized_errors = normalize_breaking_errors(errors)
    base_hash = contract_sha256(base_contract)
    current_hash = contract_sha256(current_contract)
    errors_hash = errors_sha256(normalized_errors)
    for transition in transitions:
        if (
            transition.base_contract_sha256 == base_hash
            and transition.current_contract_sha256 == current_hash
            and transition.breaking_errors_sha256 == errors_hash
            and transition.breaking_errors == tuple(normalized_errors)
        ):
            return transition
    return None


def is_breaking_transition_approved(
    base_contract: bytes,
    current_contract: bytes,
    errors: list[str],
    transitions: tuple[BreakingTransition, ...],
) -> bool:
    return (
        find_approved_breaking_transition(
            base_contract,
            current_contract,
            errors,
            transitions,
        )
        is not None
    )


def load_yaml_text(text: str) -> dict[str, Any]:
    document = yaml.safe_load(text)
    if not isinstance(document, dict):
        raise ValueError("OpenAPI document must be an object")
    return document


def load_base_contract_bytes(base_ref: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{CONTRACT_PATH.as_posix()}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return result.stdout


def load_base_contract(base_ref: str) -> dict[str, Any]:
    return load_yaml_text(load_base_contract_bytes(base_ref).decode("utf-8"))


def resolve_local_ref(document: Mapping[str, Any], value: Any) -> Any:
    if not isinstance(value, dict) or set(value) != {"$ref"}:
        return value
    reference = value["$ref"]
    if not isinstance(reference, str) or not reference.startswith("#/"):
        return value
    resolved: Any = document
    for token in reference[2:].split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(resolved, Mapping) or key not in resolved:
            return value
        resolved = resolved[key]
    return resolved


def operation_map(document: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    operations: dict[tuple[str, str], dict[str, Any]] = {}
    paths = document.get("paths", {})
    if not isinstance(paths, Mapping):
        return operations
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, Mapping):
            continue
        for method, operation in path_item.items():
            if method in HTTP_METHODS and isinstance(operation, dict):
                operations[(path, method)] = operation
    return operations


def parameter_map(
    document: Mapping[str, Any],
    path: str,
    operation: Mapping[str, Any],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    parameters: dict[tuple[str, str], Mapping[str, Any]] = {}
    paths = document.get("paths", {})
    path_item = paths.get(path, {}) if isinstance(paths, Mapping) else {}
    parameter_sources = (
        path_item.get("parameters", []) if isinstance(path_item, Mapping) else [],
        operation.get("parameters", []),
    )
    for raw_parameters in parameter_sources:
        if not isinstance(raw_parameters, list):
            continue
        for raw_parameter in raw_parameters:
            parameter = resolve_local_ref(document, raw_parameter)
            if not isinstance(parameter, Mapping):
                continue
            name = parameter.get("name")
            location = parameter.get("in")
            if isinstance(name, str) and isinstance(location, str):
                parameters[(location, name)] = parameter
    return parameters


def compare_schema_structure(
    base_document: Mapping[str, Any],
    current_document: Mapping[str, Any],
    resolved_base: Mapping[str, Any],
    resolved_current: Mapping[str, Any],
    location: str,
    errors: list[str],
) -> None:
    base_required = set(resolved_base.get("required", []))
    current_required = set(resolved_current.get("required", []))
    if base_required != current_required:
        errors.append(f"{location}: required properties changed")

    base_properties = resolved_base.get("properties", {})
    current_properties = resolved_current.get("properties", {})
    if isinstance(base_properties, Mapping):
        if not isinstance(current_properties, Mapping):
            errors.append(f"{location}: object properties were removed")
            return
        for name, property_schema in base_properties.items():
            if name not in current_properties:
                errors.append(f"{location}: property removed: {name}")
                continue
            compare_schema(
                base_document,
                current_document,
                property_schema,
                current_properties[name],
                f"{location}.{name}",
                errors,
            )

    base_items = resolved_base.get("items")
    current_items = resolved_current.get("items")
    if base_items is not None:
        if current_items is None:
            errors.append(f"{location}: array items schema removed")
        else:
            compare_schema(
                base_document,
                current_document,
                base_items,
                current_items,
                f"{location}[]",
                errors,
            )


def compare_schema(
    base_document: Mapping[str, Any],
    current_document: Mapping[str, Any],
    base_schema: Any,
    current_schema: Any,
    location: str,
    errors: list[str],
) -> None:
    resolved_base = resolve_local_ref(base_document, base_schema)
    resolved_current = resolve_local_ref(current_document, current_schema)
    if not isinstance(resolved_base, Mapping) or not isinstance(resolved_current, Mapping):
        if resolved_base != resolved_current:
            errors.append(f"{location}: schema changed incompatibly")
        return

    base_variants = resolved_base.get("oneOf")
    current_variants = resolved_current.get("oneOf")
    if isinstance(base_variants, list):
        candidate_variants = (
            current_variants if isinstance(current_variants, list) else [resolved_current]
        )
        for base_variant in base_variants:
            for current_variant in candidate_variants:
                variant_errors: list[str] = []
                compare_schema(
                    base_document,
                    current_document,
                    base_variant,
                    current_variant,
                    location,
                    variant_errors,
                )
                if not variant_errors:
                    break
            else:
                errors.append(f"{location}: backward-compatible schema branch was removed")
                return
        return

    if isinstance(current_variants, list):
        for variant in current_variants:
            variant_errors: list[str] = []
            compare_schema(
                base_document,
                current_document,
                resolved_base,
                variant,
                location,
                variant_errors,
            )
            if not variant_errors:
                return
        errors.append(f"{location}: no backward-compatible schema branch remains")
        return

    for keyword in ("type", "const"):
        if keyword in resolved_base and resolved_base.get(keyword) != resolved_current.get(keyword):
            errors.append(f"{location}: {keyword} changed")

    base_enum = resolved_base.get("enum")
    current_enum = resolved_current.get("enum")
    if isinstance(base_enum, list) and (
        not isinstance(current_enum, list) or set(base_enum) != set(current_enum)
    ):
        errors.append(f"{location}: enum values changed")
    compare_schema_structure(
        base_document,
        current_document,
        resolved_base,
        resolved_current,
        location,
        errors,
    )


def compare_content(
    base_document: Mapping[str, Any],
    current_document: Mapping[str, Any],
    base_container: Any,
    current_container: Any,
    location: str,
    errors: list[str],
) -> None:
    resolved_base = resolve_local_ref(base_document, base_container)
    resolved_current = resolve_local_ref(current_document, current_container)
    if not isinstance(resolved_base, Mapping):
        return
    if not isinstance(resolved_current, Mapping):
        errors.append(f"{location}: definition removed")
        return

    base_content = resolved_base.get("content", {})
    current_content = resolved_current.get("content", {})
    if not isinstance(base_content, Mapping):
        return
    if not isinstance(current_content, Mapping):
        errors.append(f"{location}: content removed")
        return
    for media_type, base_media in base_content.items():
        current_media = current_content.get(media_type)
        if not isinstance(base_media, Mapping):
            continue
        if not isinstance(current_media, Mapping):
            errors.append(f"{location}: media type removed: {media_type}")
            continue
        compare_schema(
            base_document,
            current_document,
            base_media.get("schema", {}),
            current_media.get("schema", {}),
            f"{location} {media_type}",
            errors,
        )


def compare_parameters(
    base_document: Mapping[str, Any],
    current_document: Mapping[str, Any],
    path: str,
    base_operation: Mapping[str, Any],
    current_operation: Mapping[str, Any],
    label: str,
    errors: list[str],
) -> None:
    base_parameters = parameter_map(base_document, path, base_operation)
    current_parameters = parameter_map(current_document, path, current_operation)
    for parameter_key, base_parameter in base_parameters.items():
        current_parameter = current_parameters.get(parameter_key)
        if current_parameter is None:
            errors.append(f"{label}: parameter removed: {parameter_key}")
            continue
        if not base_parameter.get("required") and current_parameter.get("required"):
            errors.append(f"{label}: parameter became required: {parameter_key}")
        compare_schema(
            base_document,
            current_document,
            base_parameter.get("schema", {}),
            current_parameter.get("schema", {}),
            f"{label} parameter {parameter_key}",
            errors,
        )
    for parameter_key, current_parameter in current_parameters.items():
        if parameter_key not in base_parameters and current_parameter.get("required"):
            errors.append(f"{label}: required parameter added: {parameter_key}")


def compare_request_body(
    base_document: Mapping[str, Any],
    current_document: Mapping[str, Any],
    base_operation: Mapping[str, Any],
    current_operation: Mapping[str, Any],
    label: str,
    errors: list[str],
) -> None:
    base_body = resolve_local_ref(base_document, base_operation.get("requestBody"))
    current_body = resolve_local_ref(current_document, current_operation.get("requestBody"))
    if base_body is None:
        if isinstance(current_body, Mapping) and current_body.get("required"):
            errors.append(f"{label}: required request body added")
        return
    if current_body is None:
        errors.append(f"{label}: request body removed")
        return
    if not isinstance(base_body, Mapping) or not isinstance(current_body, Mapping):
        return
    if not base_body.get("required") and current_body.get("required"):
        errors.append(f"{label}: request body became required")
    compare_content(
        base_document,
        current_document,
        base_body,
        current_body,
        f"{label} request body",
        errors,
    )


def compare_responses(
    base_document: Mapping[str, Any],
    current_document: Mapping[str, Any],
    base_operation: Mapping[str, Any],
    current_operation: Mapping[str, Any],
    label: str,
    errors: list[str],
) -> None:
    base_responses = base_operation.get("responses", {})
    current_responses = current_operation.get("responses", {})
    if not isinstance(base_responses, Mapping):
        return
    if not isinstance(current_responses, Mapping):
        errors.append(f"{label}: responses removed")
        return
    for status, base_response in base_responses.items():
        if status not in current_responses:
            errors.append(f"{label}: response removed: {status}")
            continue
        compare_content(
            base_document,
            current_document,
            base_response,
            current_responses[status],
            f"{label} response {status}",
            errors,
        )


def compare_operations(
    base_document: Mapping[str, Any],
    current_document: Mapping[str, Any],
    errors: list[str],
    allowed_removed_operations: frozenset[tuple[str, str]],
) -> None:
    base_operations = operation_map(base_document)
    current_operations = operation_map(current_document)
    for key, base_operation in base_operations.items():
        path, method = key
        label = f"{method.upper()} {path}"
        current_operation = current_operations.get(key)
        if current_operation is None:
            if key not in allowed_removed_operations:
                errors.append(f"{label}: operation removed")
            continue
        if base_operation.get("operationId") != current_operation.get("operationId"):
            errors.append(f"{label}: operationId changed")

        compare_parameters(
            base_document,
            current_document,
            path,
            base_operation,
            current_operation,
            label,
            errors,
        )
        compare_request_body(
            base_document,
            current_document,
            base_operation,
            current_operation,
            label,
            errors,
        )
        compare_responses(
            base_document,
            current_document,
            base_operation,
            current_operation,
            label,
            errors,
        )


def find_breaking_changes(
    base_document: Mapping[str, Any],
    current_document: Mapping[str, Any],
    *,
    allowed_removed_operations: frozenset[tuple[str, str]] = frozenset(),
    allowed_removed_schemas: frozenset[str] = frozenset(),
) -> list[str]:
    errors: list[str] = []
    compare_operations(
        base_document,
        current_document,
        errors,
        allowed_removed_operations,
    )

    base_schemas = base_document.get("components", {}).get("schemas", {})
    current_schemas = current_document.get("components", {}).get("schemas", {})
    if isinstance(base_schemas, Mapping) and isinstance(current_schemas, Mapping):
        for name, base_schema in base_schemas.items():
            if name not in current_schemas:
                if name not in allowed_removed_schemas:
                    errors.append(f"component schema removed: {name}")
                continue
            compare_schema(
                base_document,
                current_document,
                base_schema,
                current_schemas[name],
                f"components.schemas.{name}",
                errors,
            )
    return sorted(set(errors))


def find_partition_aware_breaking_changes(
    base_document: Mapping[str, Any],
    current_document: Mapping[str, Any],
    planned_document: Mapping[str, Any],
) -> list[str]:
    allowed_operations: set[tuple[str, str]] = set()
    allowed_schemas: set[str] = set()
    is_initial_partition = (
        base_document.get("x-shanhai-contract-kind") is None
        and current_document.get("x-shanhai-contract-kind") == "runtime"
        and planned_document.get("x-shanhai-contract-kind") == "planned"
    )
    if is_initial_partition:
        base_operations = operation_map(base_document)
        current_operations = operation_map(current_document)
        planned_operations = operation_map(planned_document)
        for key, base_operation in base_operations.items():
            planned_operation = planned_operations.get(key)
            if key in current_operations or planned_operation is None:
                continue
            if planned_operation.get(
                "x-shanhai-availability"
            ) == "planned" and normalize_partition_value(
                base_operation
            ) == normalize_partition_value(planned_operation):
                allowed_operations.add(key)

        base_schemas = base_document.get("components", {}).get("schemas", {})
        current_schemas = current_document.get("components", {}).get("schemas", {})
        planned_schemas = planned_document.get("components", {}).get("schemas", {})
        if all(
            isinstance(schemas, Mapping)
            for schemas in (base_schemas, current_schemas, planned_schemas)
        ):
            for name, base_schema in base_schemas.items():
                if name not in current_schemas and planned_schemas.get(name) == base_schema:
                    allowed_schemas.add(name)

    return find_breaking_changes(
        base_document,
        current_document,
        allowed_removed_operations=frozenset(allowed_operations),
        allowed_removed_schemas=frozenset(allowed_schemas),
    )


def normalize_partition_value(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize_partition_value(item) for item in value]
    if not isinstance(value, Mapping):
        return value
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key == "x-shanhai-availability":
            continue
        if key == "$ref" and isinstance(item, str):
            item = item.removeprefix("./api-surface.openapi.yaml")
        normalized[str(key)] = normalize_partition_value(item)
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    args = parser.parse_args()
    try:
        base_contract = load_base_contract_bytes(args.base_ref)
        current_contract = (ROOT / CONTRACT_PATH).read_bytes()
        base_document = load_yaml_text(base_contract.decode("utf-8"))
        current_document = load_yaml_text(current_contract.decode("utf-8"))
        planned_document = load_yaml_text(
            (ROOT / PLANNED_CONTRACT_PATH).read_text(encoding="utf-8")
        )
        transitions = parse_breaking_transitions(
            json.loads((ROOT / BREAKING_TRANSITIONS_PATH).read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"cannot load OpenAPI contracts: {type(exc).__name__}", file=sys.stderr)
        return 2

    errors = find_partition_aware_breaking_changes(
        base_document,
        current_document,
        planned_document,
    )
    if errors:
        transition = find_approved_breaking_transition(
            base_contract,
            current_contract,
            errors,
            transitions,
        )
        if transition is not None:
            print(
                "OpenAPI compatibility check passed with approved breaking transition "
                f"{transition.id} (Issue #{transition.issue}) against {args.base_ref}"
            )
            return 0
        for error in errors:
            print(f"breaking OpenAPI change: {error}", file=sys.stderr)
        print(
            "breaking OpenAPI changes do not exactly match an approved transition",
            file=sys.stderr,
        )
        return 1
    print(f"OpenAPI compatibility check passed against {args.base_ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
