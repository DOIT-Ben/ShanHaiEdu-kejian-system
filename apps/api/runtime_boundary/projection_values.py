"""Restricted value projections shared by runtime-boundary compilers."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any, cast

from apps.api.runtime_boundary.ports import (
    RuntimeNodeDefinition,
    WorkflowExecutionContext,
)

MAX_POINTER_LENGTH = 2_048
MAX_POINTER_DEPTH = 64
_POINTER_SEGMENT = re.compile(r"^(?:[^~/\\#\x00-\x1f\x7f]|~0|~1)*$")
_CANONICAL_INDEX = re.compile(r"^(?:0|[1-9][0-9]*)$")
_TRUSTED_RUNTIME_ROOTS = frozenset(
    {"lesson_key", "lesson_unit_id", "project_id", "workflow_run_id", "node_run_id"}
)
_ALLOWED_RUNTIME_VALUE_ROOTS = frozenset({"relation_keys", "reference_assets"})


class OutputProjectionError(ValueError):
    """Raised when a published output projection cannot be compiled safely."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


ProjectionCompilationError = OutputProjectionError


def resolve_projection(
    raw: object,
    *,
    output: Mapping[str, Any],
    item: Mapping[str, Any] | None,
    runtime: Mapping[str, Any],
) -> object:
    declaration = require_mapping(raw, "OUTPUT_PROJECTION_VALUE_INVALID")
    source = cast(object, declaration.get("source"))
    if source == "constant":
        if set(declaration) != {"source", "value"}:
            raise OutputProjectionError(
                "OUTPUT_PROJECTION_VALUE_INVALID",
                "constant projection contains extra fields",
            )
        value = cast(object, declaration.get("value"))
        validate_json_value(value)
        return value
    if source == "intrinsic":
        return _resolve_intrinsic(declaration, runtime)
    if source not in {"output", "item", "runtime"}:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_VALUE_INVALID",
            "projection source is unsupported",
        )
    if set(declaration) != {"source", "pointer"}:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_VALUE_INVALID",
            "pointer projection contains extra fields",
        )
    pointer = declaration.get("pointer")
    if not isinstance(pointer, str):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_INVALID",
            "projection pointer must be a string",
        )
    if source == "runtime" and not _is_allowed_runtime_pointer(pointer):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_RUNTIME_POINTER_INVALID",
            "runtime projections may expose only lesson_key or relation keys",
        )
    pointer_source = cast(str, source)
    document = _projection_document(pointer_source, output=output, item=item, runtime=runtime)
    return resolve_json_pointer(document, pointer, source=pointer_source)


def _is_allowed_runtime_pointer(pointer: str) -> bool:
    return pointer in {"/lesson_key", "/reference_assets"} or pointer.startswith("/relation_keys/")


def _resolve_intrinsic(declaration: Mapping[str, Any], runtime: Mapping[str, Any]) -> object:
    if declaration != {"source": "intrinsic", "name": "item_position"}:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_VALUE_INVALID",
            "unsupported intrinsic projection",
        )
    if "item_position" not in runtime:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_INTRINSIC_CONTEXT_MISSING",
            "item_position is only available for package items",
        )
    return runtime["item_position"]


def _projection_document(
    source: str,
    *,
    output: Mapping[str, Any],
    item: Mapping[str, Any] | None,
    runtime: Mapping[str, Any],
) -> object:
    if source == "output":
        return output
    if source == "runtime":
        return runtime
    if item is None:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ITEM_CONTEXT_MISSING",
            "item projection is only valid for package items",
        )
    return item


def resolve_json_pointer(document: object, pointer: str, *, source: str) -> object:
    parts = _decode_pointer(pointer, source=source)
    current = document
    for part in parts:
        if isinstance(current, Mapping):
            current = _mapping_pointer_value(cast(Mapping[object, object], current), part, pointer)
            continue
        if isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            current = _sequence_pointer_value(cast(Sequence[object], current), part, pointer)
            continue
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_TYPE_INVALID",
            f"projection pointer traverses a non-container: {pointer}",
        )
    return current


def _decode_pointer(pointer: str, *, source: str) -> tuple[str, ...]:
    if len(pointer) > MAX_POINTER_LENGTH or (pointer and not pointer.startswith("/")):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_INVALID",
            f"{source} pointer must be an RFC 6901 absolute pointer",
        )
    if pointer == "":
        return ()
    parts = pointer.split("/")[1:]
    if len(parts) > MAX_POINTER_DEPTH:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_INVALID", "projection pointer is too deep"
        )
    return tuple(_decode_pointer_part(part) for part in parts)


def _decode_pointer_part(raw_part: str) -> str:
    unsafe_token = any(token in raw_part for token in ("*", "[", "]"))
    if _POINTER_SEGMENT.fullmatch(raw_part) is None or raw_part in {"-", ".", ".."} or unsafe_token:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_INVALID",
            "projection pointer contains an unsafe segment",
        )
    return raw_part.replace("~1", "/").replace("~0", "~")


def _mapping_pointer_value(value: Mapping[object, object], part: str, pointer: str) -> object:
    if part not in value:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_MISSING",
            f"projection pointer does not resolve: {pointer}",
        )
    return value[part]


def _sequence_pointer_value(value: Sequence[object], part: str, pointer: str) -> object:
    if _CANONICAL_INDEX.fullmatch(part) is None:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_INVALID",
            "array pointer segment must be a canonical index",
        )
    index = int(part)
    if index >= len(value):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POINTER_MISSING",
            f"projection pointer does not resolve: {pointer}",
        )
    return value[index]


def runtime_document(
    execution: WorkflowExecutionContext,
    runtime_values: Mapping[str, Any] | None,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if runtime_values is not None:
        values = dict(
            require_json_mapping(
                runtime_values,
                "OUTPUT_PROJECTION_RUNTIME_CONTEXT_INVALID",
            )
        )
    unsafe = set(values) - _ALLOWED_RUNTIME_VALUE_ROOTS
    if unsafe:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_RUNTIME_CONTEXT_INVALID",
            f"runtime projection contains forbidden roots: {sorted(unsafe)}",
        )
    trusted = {
        "lesson_key": execution.lesson_key,
        "lesson_unit_id": str(execution.lesson_unit_id)
        if execution.lesson_unit_id is not None
        else None,
        "project_id": str(execution.project_id),
        "workflow_run_id": str(execution.workflow_run_id),
        "node_run_id": str(execution.node_run_id),
    }
    assert not set(values) & _TRUSTED_RUNTIME_ROOTS
    return {**trusted, **values}


def validate_resolved_binding(
    definition: RuntimeNodeDefinition, binding: Mapping[str, Any]
) -> None:
    if binding.get("node_key") != definition.node_key:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_BINDING_NODE_MISMATCH",
            "published binding does not match the resolved node",
        )
    generation_ref = require_mapping(
        binding.get("generation_template_ref"),
        "OUTPUT_PROJECTION_GENERATION_TEMPLATE_MISMATCH",
    )
    if (
        generation_ref.get("kind") != "generation_template"
        or generation_ref.get("item_key") != definition.generation_template_key
    ):
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_GENERATION_TEMPLATE_MISMATCH",
            "published binding does not match the resolved generation template",
        )


def validate_scope_context(execution: WorkflowExecutionContext, scope: object) -> None:
    if scope == "project":
        if execution.lesson_unit_id is not None or execution.lesson_key is not None:
            raise OutputProjectionError(
                "OUTPUT_PROJECTION_SCOPE_MISMATCH",
                "project-scope output cannot carry a lesson context",
            )
        return
    if scope == "lesson_unit":
        if execution.lesson_unit_id is None or not execution.lesson_key:
            raise OutputProjectionError(
                "OUTPUT_PROJECTION_SCOPE_MISSING",
                "lesson-unit output requires lesson_unit_id and lesson_key",
            )
        return
    raise OutputProjectionError(
        "OUTPUT_PROJECTION_SCOPE_INVALID",
        "published binding has an invalid execution scope",
    )


def validate_artifact_declaration(binding: Mapping[str, Any], artifact: Mapping[str, Any]) -> None:
    scope = binding.get("execution_scope")
    identity = require_mapping(artifact.get("identity"), "OUTPUT_PROJECTION_IDENTITY_INVALID")
    expected_strategy = "project_singleton" if scope == "project" else "lesson_unit_singleton"
    if identity.get("strategy") != expected_strategy:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_IDENTITY_SCOPE_MISMATCH",
            "artifact identity does not match the execution scope",
        )
    expected_branch = "project" if scope == "project" else binding.get("branch_key")
    if artifact.get("branch_key") != expected_branch:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_ARTIFACT_BRANCH_MISMATCH",
            "artifact branch does not match the execution scope",
        )


def require_mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OutputProjectionError(code, "expected a JSON object")
    entries = cast(Mapping[object, object], value)
    if any(type(key) is not str for key in entries):
        raise OutputProjectionError(code, "expected a JSON object")
    return cast(Mapping[str, Any], entries)


def require_json_mapping(value: object, code: str) -> Mapping[str, Any]:
    mapping = require_mapping(value, code)
    validate_json_value(mapping)
    return mapping


def require_text(value: object, field: str, maximum: int) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise OutputProjectionError("OUTPUT_PROJECTION_FIELD_INVALID", f"{field} is invalid")
    return value


def optional_text(value: object, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    return require_text(value, field, maximum)


def require_position(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 1:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_POSITION_INVALID",
            "package item position must be a positive integer",
        )
    return value


def require_text_sequence(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise OutputProjectionError(code, "expected an array of strings")
    raw_values = tuple(cast(Sequence[object], value))
    if any(type(item) is not str or not item.strip() for item in raw_values):
        raise OutputProjectionError(code, "expected an array of strings")
    return tuple(cast(str, item) for item in raw_values)


def validate_json_value(value: object) -> None:
    try:
        json.dumps(
            plain_json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise OutputProjectionError(
            "OUTPUT_PROJECTION_JSON_INVALID",
            "projection value must be finite JSON",
        ) from exc


def plain_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, child in cast(Mapping[object, object], value).items():
            if type(key) is not str:
                raise TypeError("JSON object keys must be strings")
            result[key] = plain_json_value(child)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [plain_json_value(child) for child in cast(Sequence[object], value)]
    return value


def freeze_json_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    frozen = freeze_json_value(value)
    assert isinstance(frozen, Mapping)
    return cast(Mapping[str, Any], frozen)


def freeze_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, child in cast(Mapping[object, object], value).items():
            if type(key) is not str:
                raise OutputProjectionError(
                    "OUTPUT_PROJECTION_JSON_INVALID",
                    "projection object keys must be strings",
                )
            frozen[key] = freeze_json_value(child)
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(freeze_json_value(child) for child in cast(Sequence[object], value))
    return value
