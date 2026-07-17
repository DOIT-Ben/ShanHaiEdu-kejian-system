"""Compile an approved Markdown template draft into a V1 content package."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, SchemaError

from workflow.content_package import (
    DEFAULT_CONTEXT_SOURCES,
    ContentPackageValidationError,
    resolve_content_package_item_path,
    validate_content_package,
)
from workflow.markdown_template_content_package import (
    ITEM_SUFFIXES,
    build_compiled_items,
    build_compiled_manifest,
)

PROFILE_SCHEMA_FILE = "markdown-template-compilation-profile.schema.json"
DRAFT_SCHEMA_FILE = "markdown-template-draft.schema.json"
REQUEST_FIELD_KEY = "request.instructions"
MAX_COMPILED_KEY_CHARS = 160


class MarkdownTemplateCompilationError(ValueError):
    """Raised when a reviewed draft cannot become a safe content package."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CompiledMarkdownTemplatePackage:
    """An in-memory package ready for deterministic validated writing."""

    manifest: dict[str, Any]
    items: Mapping[str, dict[str, Any]]
    contracts_root: Path = field(repr=False, compare=False)


def compile_markdown_template(
    draft: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    contracts_root: Path,
) -> CompiledMarkdownTemplatePackage:
    """Compile a schema-valid ready draft without re-reading source Markdown."""

    root = contracts_root.resolve()
    _validate_instance(draft, root / DRAFT_SCHEMA_FILE, "MARKDOWN_COMPILE_DRAFT_INVALID")
    if draft["state"] != "ready":
        raise MarkdownTemplateCompilationError(
            "MARKDOWN_COMPILE_DRAFT_NOT_READY",
            "TemplateDraft must be approved before compilation",
        )
    _validate_instance(
        profile,
        root / PROFILE_SCHEMA_FILE,
        "MARKDOWN_COMPILE_PROFILE_INVALID",
    )
    _validate_context_bindings(profile)
    _validate_draft_keys(draft)

    prefix = cast(str, profile["key_prefix"])
    item_keys = {suffix: f"{prefix}.{suffix}" for suffix, _, _ in ITEM_SUFFIXES}
    sections = cast(list[dict[str, Any]], draft["sections"])
    input_fields = _build_input_fields(sections)
    output_fields = [_build_output_field(section) for section in sections]
    items = build_compiled_items(draft, profile, item_keys, input_fields, output_fields)
    manifest = build_compiled_manifest(draft, profile, root, item_keys, items)
    return CompiledMarkdownTemplatePackage(
        manifest=manifest,
        items=items,
        contracts_root=root,
    )


def write_compiled_content_package(
    compiled: CompiledMarkdownTemplatePackage,
    output_root: Path,
) -> None:
    """Atomically write and validate a compiled package without overwriting paths."""

    output = output_root.resolve()
    if output.exists():
        raise MarkdownTemplateCompilationError(
            "MARKDOWN_COMPILE_OUTPUT_EXISTS",
            f"Output path already exists: {output.name}",
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        for entry in cast(list[dict[str, Any]], compiled.manifest["items"]):
            item_path = resolve_content_package_item_path(
                temporary,
                cast(str, entry["path"]),
            )
            item_path.parent.mkdir(parents=True, exist_ok=True)
            _write_json(item_path, compiled.items[cast(str, entry["item_key"])])
        _write_json(temporary / "manifest.json", compiled.manifest)
        try:
            validate_content_package(temporary, contracts_root=compiled.contracts_root)
        except ContentPackageValidationError as exc:
            raise MarkdownTemplateCompilationError(
                "MARKDOWN_COMPILE_PACKAGE_INVALID",
                f"Compiled content package failed validation: {exc.code}",
            ) from exc
        temporary.rename(output)
    except MarkdownTemplateCompilationError:
        raise
    except OSError as exc:
        if output.exists():
            code = "MARKDOWN_COMPILE_OUTPUT_EXISTS"
        else:
            code = "MARKDOWN_COMPILE_WRITE_FAILED"
        raise MarkdownTemplateCompilationError(
            code,
            "Cannot write compiled content package",
        ) from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _validate_instance(value: Mapping[str, Any], schema_path: Path, code: str) -> None:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = cast(Any, Draft202012Validator(schema))
        errors = sorted(
            validator.iter_errors(value),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SchemaError) as exc:
        raise MarkdownTemplateCompilationError(
            "MARKDOWN_COMPILE_CONTRACT_UNAVAILABLE",
            f"Cannot load compiler contract: {schema_path.name}",
        ) from exc
    if errors:
        error = errors[0]
        path = "/".join(str(part) for part in error.absolute_path)
        location = f" at {path}" if path else ""
        raise MarkdownTemplateCompilationError(code, f"{error.message}{location}")


def _validate_context_bindings(profile: Mapping[str, Any]) -> None:
    bindings = cast(list[dict[str, Any]], profile["context_bindings"])
    keys: set[str] = set()
    for binding in bindings:
        binding_key = cast(str, binding["binding_key"])
        source = cast(str, binding["source"])
        if binding_key in keys or source not in DEFAULT_CONTEXT_SOURCES:
            raise MarkdownTemplateCompilationError(
                "MARKDOWN_COMPILE_PROFILE_INVALID",
                "CompilationProfile contains duplicate or forbidden context bindings",
            )
        keys.add(binding_key)


def _validate_draft_keys(draft: Mapping[str, Any]) -> None:
    keys: set[str] = set()
    for section in cast(list[dict[str, Any]], draft["sections"]):
        candidates = [cast(str, section["section_key"])]
        if section["body_markdown"] and section["subsections"]:
            candidates.append(f"{section['section_key']}.content")
        candidates.extend(
            cast(str, subsection["subsection_key"])
            for subsection in cast(list[dict[str, Any]], section["subsections"])
        )
        for key in candidates:
            if len(key) > MAX_COMPILED_KEY_CHARS:
                raise MarkdownTemplateCompilationError(
                    "MARKDOWN_COMPILE_KEY_INVALID",
                    f"Compiled field key exceeds {MAX_COMPILED_KEY_CHARS} characters",
                )
            if key in keys:
                raise MarkdownTemplateCompilationError(
                    "MARKDOWN_COMPILE_KEY_COLLISION",
                    f"Duplicate compiled field key: {key}",
                )
            keys.add(key)


def _build_input_fields(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = [
        {
            "field_key": REQUEST_FIELD_KEY,
            "label": "补充要求",
            "description": "教师对本次生成提出的补充业务要求。",
            "value_type": "rich_text",
            "required": False,
            "source": "teacher",
            "visibility": "secondary",
            "widget": "textarea",
        }
    ]
    used_keys = {REQUEST_FIELD_KEY}
    for section in sections:
        if section["content_mode"] not in {"teacher_input", "mixed"}:
            continue
        for key, label, body in _section_leaves(section):
            if key in used_keys:
                raise MarkdownTemplateCompilationError(
                    "MARKDOWN_COMPILE_KEY_COLLISION",
                    f"Duplicate input field key: {key}",
                )
            field_value: dict[str, Any] = {
                "field_key": key,
                "label": label,
                "value_type": "rich_text",
                "required": cast(bool, section["required"]),
                "source": "teacher",
                "visibility": "primary" if section["visible"] else "hidden",
                "widget": "textarea",
            }
            if body:
                field_value["default_value"] = body
            fields.append(field_value)
            used_keys.add(key)
    return fields


def _build_output_field(section: dict[str, Any]) -> dict[str, Any]:
    subsections = cast(list[dict[str, Any]], section["subsections"])
    if subsections:
        children = [
            _build_leaf_output_field(key, label, body, section)
            for key, label, body in _section_leaves(section)
        ]
        return {
            **_common_output_field(section["section_key"], section["title"], section),
            "type": "repeatable" if section["repeatable"] else "group",
            "repeatable": cast(bool, section["repeatable"]),
            "children": children,
        }
    return _build_leaf_output_field(
        cast(str, section["section_key"]),
        cast(str, section["title"]),
        cast(str, section["body_markdown"]),
        section,
        field_type="repeatable" if section["repeatable"] else "rich_text",
    )


def _section_leaves(section: dict[str, Any]) -> list[tuple[str, str, str]]:
    leaves: list[tuple[str, str, str]] = []
    body = cast(str, section["body_markdown"])
    subsections = cast(list[dict[str, Any]], section["subsections"])
    if body and subsections:
        leaves.append((f"{section['section_key']}.content", f"{section['title']}正文", body))
    for subsection in subsections:
        leaves.append(
            (
                cast(str, subsection["subsection_key"]),
                cast(str, subsection["title"]),
                cast(str, subsection["body_markdown"]),
            )
        )
    if not subsections:
        leaves.append(
            (
                cast(str, section["section_key"]),
                cast(str, section["title"]),
                body,
            )
        )
    return leaves


def _build_leaf_output_field(
    key: str,
    label: str,
    body: str,
    section: dict[str, Any],
    *,
    field_type: str = "rich_text",
) -> dict[str, Any]:
    value = {
        **_common_output_field(key, label, section),
        "type": field_type,
    }
    mode = cast(str, section["content_mode"])
    if body and mode in {"fixed", "teacher_input", "mixed"}:
        value["default_value"] = body
    if mode == "ai_generated":
        value["generation_instruction"] = body or f"生成{label}。"
    elif mode == "mixed":
        prefix = "在保留默认内容的基础上补充并完善" if body else "生成并完善"
        value["generation_instruction"] = f"{prefix}{label}。"
    return value


def _common_output_field(key: object, label: object, section: dict[str, Any]) -> dict[str, Any]:
    return {
        "field_key": key,
        "label": label,
        "required": cast(bool, section["required"]),
        "editable": cast(bool, section["editable"]),
        "deletable": not cast(bool, section["required"]),
        "visibility": "primary" if section["visible"] else "hidden",
    }


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )
    path.write_text(payload + "\n", encoding="utf-8", newline="\n")
