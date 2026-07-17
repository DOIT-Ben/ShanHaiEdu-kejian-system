"""Validation primitives for schema-driven content package directories."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

SCHEMA_FILES = {
    "input_definition": "input-definition.schema.json",
    "content_definition": "content-definition.schema.json",
    "style_preset": "style-preset.schema.json",
    "prompt_template": "prompt-template.schema.json",
    "projection_template": "projection-template.schema.json",
    "generation_template": "generation-template.schema.json",
}

IDENTITY_FIELDS = {
    "input_definition": "definition_key",
    "content_definition": "definition_key",
    "style_preset": "preset_key",
    "prompt_template": "template_key",
    "projection_template": "projection_key",
    "generation_template": "template_key",
}

DEFAULT_CONTEXT_SOURCES = frozenset(
    {
        "asset_slot.current_version",
        "intro_selection.snapshot",
        "lesson_division.approved_version",
        "lesson_plan.approved_version",
        "material.approved_parse",
        "project.teacher_preferences",
    }
)
PROJECTION_VARIABLE = re.compile(r"\{\{([a-z][a-z0-9_.-]{1,159})\}\}")
MAX_CONTENT_PACKAGE_JSON_BYTES = 5_000_000
WINDOWS_RESERVED_NAMES = frozenset(
    {"AUX", "CON", "NUL", "PRN"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


class ContentPackageValidationError(ValueError):
    """Raised when a content package cannot be safely imported."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ValidatedContentPackage:
    manifest: dict[str, Any]
    items: Mapping[str, dict[str, Any]]


def canonical_json_sha256(value: Mapping[str, Any]) -> str:
    """Hash semantic JSON content independently from file spacing and line endings."""

    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_content_package(
    package_root: Path,
    *,
    contracts_root: Path,
    allowed_context_sources: frozenset[str] = DEFAULT_CONTEXT_SOURCES,
) -> ValidatedContentPackage:
    """Validate an extracted package directory against the V1 source contract."""

    root = package_root.resolve()
    manifest = _load_object(resolve_content_package_item_path(root, "manifest.json"))
    _validate_schema(
        manifest,
        _load_object(contracts_root / "content-package-manifest.schema.json"),
        code="PACKAGE_MANIFEST_INVALID",
    )
    common_schema = _load_object(contracts_root / "content-item.schema.json")
    manifest_items = cast(list[dict[str, Any]], manifest["items"])
    entries: dict[str, dict[str, Any]] = {}
    kinds: dict[str, str] = {}

    for entry in manifest_items:
        item_key = cast(str, entry["item_key"])
        kind = cast(str, entry["kind"])
        if item_key in entries:
            raise ContentPackageValidationError(
                "PACKAGE_DUPLICATE_ITEM_KEY",
                f"duplicate item_key: {item_key}",
            )
        item = _validate_manifest_item(root, contracts_root, common_schema, entry)
        entries[item_key] = item
        kinds[item_key] = kind

    _validate_references(entries, kinds)
    _validate_entrypoints(cast(list[str], manifest["entrypoints"]), kinds)
    _validate_context_sources(entries, allowed_context_sources)
    _validate_logical_keys(entries)
    _validate_projection_variables(entries)
    return ValidatedContentPackage(manifest=manifest, items=entries)


def _validate_manifest_item(
    root: Path,
    contracts_root: Path,
    common_schema: dict[str, Any],
    entry: dict[str, Any],
) -> dict[str, Any]:
    item_key = cast(str, entry["item_key"])
    kind = cast(str, entry["kind"])
    item_path = resolve_content_package_item_path(root, cast(str, entry["path"]))
    item = _load_object(item_path)
    _validate_schema(item, common_schema, code="PACKAGE_ITEM_ENVELOPE_INVALID")
    if item["kind"] != kind or item["metadata"]["key"] != item_key:
        raise ContentPackageValidationError(
            "PACKAGE_ITEM_IDENTITY_MISMATCH",
            f"manifest identity does not match {entry['path']}",
        )

    expected_schema = _load_object(contracts_root / SCHEMA_FILES[kind])
    if entry["schema_id"] != expected_schema["$id"]:
        raise ContentPackageValidationError(
            "PACKAGE_SCHEMA_ID_MISMATCH",
            f"unexpected schema_id for {item_key}",
        )
    spec = cast(dict[str, Any], item["spec"])
    _validate_schema(spec, expected_schema, code="PACKAGE_ITEM_SPEC_INVALID")
    if spec[IDENTITY_FIELDS[kind]] != item_key:
        raise ContentPackageValidationError(
            "PACKAGE_ITEM_IDENTITY_MISMATCH",
            f"spec identity does not match {item_key}",
        )
    if canonical_json_sha256(item) != entry["sha256"]:
        raise ContentPackageValidationError(
            "PACKAGE_HASH_MISMATCH",
            f"sha256 does not match {item_key}",
        )
    return item


def _load_object(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            payload = stream.read(MAX_CONTENT_PACKAGE_JSON_BYTES + 1)
        if len(payload) > MAX_CONTENT_PACKAGE_JSON_BYTES:
            raise ContentPackageValidationError(
                "PACKAGE_JSON_TOO_LARGE",
                f"JSON document exceeds size limit: {path.name}",
            )
        value = json.loads(payload.decode("utf-8"))
    except ContentPackageValidationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContentPackageValidationError(
            "PACKAGE_JSON_INVALID",
            f"cannot read JSON object: {path.name}",
        ) from exc
    if not isinstance(value, dict):
        raise ContentPackageValidationError(
            "PACKAGE_JSON_INVALID",
            f"JSON document must be an object: {path.name}",
        )
    return cast(dict[str, Any], value)


def _validate_schema(value: dict[str, Any], schema: dict[str, Any], *, code: str) -> None:
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        cast(Any, validator).validate(value)
    except ValidationError as exc:
        path = "/".join(str(part) for part in exc.absolute_path)
        suffix = f" at {path}" if path else ""
        raise ContentPackageValidationError(code, f"{exc.message}{suffix}") from exc


def resolve_content_package_item_path(root: Path, relative: str) -> Path:
    """Resolve a manifest item path without allowing it to leave the package root."""

    root = root.resolve()
    pure_path = PurePosixPath(relative)
    raw_parts = relative.split("/")
    if (
        pure_path.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
        or "\\" in relative
        or any(part.endswith(".") for part in raw_parts)
        or any(
            part.split(".", maxsplit=1)[0].upper() in WINDOWS_RESERVED_NAMES for part in raw_parts
        )
    ):
        raise ContentPackageValidationError(
            "PACKAGE_PATH_INVALID",
            f"unsafe package path: {relative}",
        )
    resolved = (root / Path(*pure_path.parts)).resolve()
    if not resolved.is_relative_to(root):
        raise ContentPackageValidationError(
            "PACKAGE_PATH_INVALID",
            f"package path leaves root: {relative}",
        )
    return resolved


def _iter_refs(value: object) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        if set(mapping) == {"item_key", "kind"}:
            item_key = mapping["item_key"]
            kind = mapping["kind"]
            if isinstance(item_key, str) and isinstance(kind, str):
                yield item_key, kind
            return
        for child in mapping.values():
            yield from _iter_refs(child)
    elif isinstance(value, list):
        for child in cast(list[object], value):
            yield from _iter_refs(child)


def _validate_references(
    entries: Mapping[str, dict[str, Any]],
    kinds: Mapping[str, str],
) -> None:
    for source_key, item in entries.items():
        for target_key, expected_kind in _iter_refs(item["spec"]):
            actual_kind = kinds.get(target_key)
            if actual_kind is None:
                raise ContentPackageValidationError(
                    "PACKAGE_REFERENCE_UNRESOLVED",
                    f"{source_key} references missing item {target_key}",
                )
            if actual_kind != expected_kind:
                raise ContentPackageValidationError(
                    "PACKAGE_REFERENCE_KIND_MISMATCH",
                    f"{source_key} expects {target_key} to be {expected_kind}",
                )


def _validate_entrypoints(entrypoints: list[str], kinds: Mapping[str, str]) -> None:
    for item_key in entrypoints:
        if kinds.get(item_key) != "generation_template":
            raise ContentPackageValidationError(
                "PACKAGE_ENTRYPOINT_INVALID",
                f"entrypoint must reference a generation_template: {item_key}",
            )


def _validate_context_sources(
    entries: Mapping[str, dict[str, Any]],
    allowed_context_sources: frozenset[str],
) -> None:
    for item_key, item in entries.items():
        if item["kind"] != "prompt_template":
            continue
        spec = cast(dict[str, Any], item["spec"])
        bindings = cast(list[dict[str, Any]], spec["context_bindings"])
        for binding in bindings:
            source = cast(str, binding["source"])
            if source not in allowed_context_sources:
                raise ContentPackageValidationError(
                    "PACKAGE_CONTEXT_SOURCE_FORBIDDEN",
                    f"{item_key} requests unregistered context source {source}",
                )


def _validate_logical_keys(entries: Mapping[str, dict[str, Any]]) -> None:
    for item_key, item in entries.items():
        kind = cast(str, item["kind"])
        spec = cast(dict[str, Any], item["spec"])
        if kind == "input_definition":
            _require_unique_values(item_key, spec["fields"], "field_key")
        elif kind == "content_definition":
            fields = cast(list[dict[str, Any]], spec["fields"])
            _require_unique_strings(
                item_key,
                [field["field_key"] for field in _iter_content_fields(fields)],
                "field_key",
            )
        elif kind == "prompt_template":
            _require_unique_values(item_key, spec["sections"], "section_key")
            _require_unique_values(item_key, spec["context_bindings"], "binding_key")
        elif kind == "generation_template":
            _require_unique_values(item_key, spec["projection_refs"], "role")


def _validate_projection_variables(entries: Mapping[str, dict[str, Any]]) -> None:
    for item_key, item in entries.items():
        if item["kind"] != "projection_template":
            continue
        spec = cast(dict[str, Any], item["spec"])
        source_key = cast(str, spec["source_definition_ref"]["item_key"])
        source_spec = cast(dict[str, Any], entries[source_key]["spec"])
        source_fields = {
            field["field_key"]
            for field in _iter_content_fields(cast(list[dict[str, Any]], source_spec["fields"]))
        }
        allowed = set(cast(list[str], spec["allowed_variables"]))
        if not allowed.issubset(source_fields):
            raise ContentPackageValidationError(
                "PACKAGE_PROJECTION_VARIABLE_FORBIDDEN",
                f"{item_key} allows variables outside {source_key}",
            )
        template = spec.get("template")
        if not isinstance(template, str):
            continue
        variables = set(PROJECTION_VARIABLE.findall(template))
        if template.count("{{") != len(PROJECTION_VARIABLE.findall(template)) or not (
            variables.issubset(allowed)
        ):
            raise ContentPackageValidationError(
                "PACKAGE_PROJECTION_VARIABLE_FORBIDDEN",
                f"{item_key} template uses undeclared variables",
            )


def _iter_content_fields(fields: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for field in fields:
        yield field
        children = cast(list[dict[str, Any]], field.get("children", []))
        yield from _iter_content_fields(children)


def _require_unique_values(
    item_key: str,
    values: object,
    key: str,
) -> None:
    items = cast(list[dict[str, Any]], values)
    _require_unique_strings(item_key, [cast(str, item[key]) for item in items], key)


def _require_unique_strings(item_key: str, values: list[str], key: str) -> None:
    if len(values) != len(set(values)):
        raise ContentPackageValidationError(
            "PACKAGE_DUPLICATE_LOGICAL_KEY",
            f"{item_key} contains duplicate {key}",
        )
