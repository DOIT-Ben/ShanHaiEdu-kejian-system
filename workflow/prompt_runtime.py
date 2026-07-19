"""Deterministic context assembly and layered prompt compilation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, cast

from workflow.content_package import DEFAULT_CONTEXT_SOURCES

ContextExposure = Literal["full", "summary", "hidden"]
PromptEditMode = Literal["replace_editable_layer"]


class PromptRuntimeError(ValueError):
    """Raised before a model call when prompt runtime policy is violated."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ContextBinding:
    binding_key: str
    source: str
    required: bool
    exposure: ContextExposure
    max_items: int
    max_bytes: int


@dataclass(frozen=True, slots=True)
class ContextItem:
    source: str
    source_id: str
    source_version_id: str | None
    content: object


@dataclass(frozen=True, slots=True)
class AssembledContext:
    bindings: tuple[dict[str, Any], ...]
    content_hash: str


@dataclass(frozen=True, slots=True)
class PromptSection:
    section_key: str
    layer: str
    content: str
    editable: bool
    visible_to_teacher: bool


@dataclass(frozen=True, slots=True)
class PromptPreview:
    editable_prompt: str
    edit_policy: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CompiledPrompt:
    template_refs: dict[str, str]
    layers: tuple[dict[str, Any], ...]
    editable_prompt: str
    user_diff: dict[str, Any]
    compiled_prompt: str
    request_schema: dict[str, Any]
    content_hash: str
    context_hash: str
    preview: PromptPreview


def assemble_context(
    bindings: tuple[ContextBinding, ...],
    values_by_source: dict[str, tuple[ContextItem, ...]],
    *,
    allowed_sources: frozenset[str] = DEFAULT_CONTEXT_SOURCES,
) -> AssembledContext:
    """Assemble only declared, registered context sources into a stable snapshot."""

    _validate_bindings(bindings, allowed_sources)
    declared_sources = {binding.source for binding in bindings}
    extra_sources = set(values_by_source) - declared_sources
    if extra_sources:
        raise PromptRuntimeError(
            "CONTEXT_SOURCE_NOT_DECLARED",
            f"context values include undeclared sources: {sorted(extra_sources)}",
        )

    assembled: list[dict[str, Any]] = []
    for binding in bindings:
        raw_items = values_by_source.get(binding.source, ())
        if binding.required and not raw_items:
            raise PromptRuntimeError(
                "CONTEXT_REQUIRED_MISSING",
                f"required context is missing: {binding.binding_key}",
            )
        if len(raw_items) > binding.max_items:
            raise PromptRuntimeError(
                "CONTEXT_ITEM_LIMIT_EXCEEDED",
                f"context item limit exceeded: {binding.binding_key}",
            )
        items = tuple(sorted(raw_items, key=_context_item_sort_key))
        serialized_items = tuple(_serialize_context_item(binding, item) for item in items)
        content_bytes = sum(len(_canonical_json(item.content)) for item in items)
        if content_bytes > binding.max_bytes:
            raise PromptRuntimeError(
                "CONTEXT_BYTE_LIMIT_EXCEEDED",
                f"context byte limit exceeded: {binding.binding_key}",
            )
        assembled.append(
            {
                "binding_key": binding.binding_key,
                "source": binding.source,
                "exposure": binding.exposure,
                "items": list(serialized_items),
            }
        )
    payload = {"bindings": assembled}
    return AssembledContext(
        bindings=tuple(assembled),
        content_hash=_sha256(payload),
    )


def compile_prompt(
    *,
    template_key: str,
    template_version: str,
    platform_safety: str,
    sections: tuple[PromptSection, ...],
    context: AssembledContext,
    output_schema: dict[str, Any],
    provider_format: str,
    user_edit_mode: PromptEditMode,
    user_edit_max_chars: int,
    user_revision: str | None = None,
) -> CompiledPrompt:
    """Compile protected and editable layers while exposing only a safe preview."""

    _validate_prompt_input(
        template_key=template_key,
        template_version=template_version,
        platform_safety=platform_safety,
        sections=sections,
        provider_format=provider_format,
        user_edit_mode=user_edit_mode,
        user_edit_max_chars=user_edit_max_chars,
        user_revision=user_revision,
    )
    user_diff: dict[str, Any] = {}
    if user_revision is not None:
        user_diff = {
            "mode": "replace_editable_layer",
            "replacement": user_revision,
        }

    effective_sections = _effective_sections(sections, user_revision)
    context_payload = {"bindings": list(context.bindings)}
    layers: list[dict[str, Any]] = [
        _layer("platform_safety", "platform_safety", platform_safety, locked=True)
    ]
    layers.extend(
        _layer(
            section.layer,
            section.section_key,
            content,
            locked=not section.editable,
        )
        for section, content in effective_sections
    )
    layers.extend(
        (
            _layer(
                "context",
                "declared_context",
                _canonical_json_text(context_payload),
                locked=True,
            ),
            _layer(
                "output_schema",
                "request_schema",
                _canonical_json_text(output_schema),
                locked=True,
            ),
            _layer("provider_format", "provider_format", provider_format, locked=True),
        )
    )
    compiled_prompt = "\n\n".join(
        f"[{layer['layer']}:{layer['key']}]\n{layer['content']}" for layer in layers
    )
    editable_prompt = _teacher_prompt(effective_sections, context)
    preview = PromptPreview(
        editable_prompt=editable_prompt,
        edit_policy={"mode": user_edit_mode, "max_chars": user_edit_max_chars},
    )
    template_refs = {"template_key": template_key, "template_version": template_version}
    snapshot_payload = {
        "template_refs": template_refs,
        "layers": layers,
        "editable_prompt": editable_prompt,
        "user_diff": user_diff,
        "compiled_prompt": compiled_prompt,
        "request_schema": output_schema,
        "context_hash": context.content_hash,
    }
    return CompiledPrompt(
        template_refs=template_refs,
        layers=tuple(layers),
        editable_prompt=editable_prompt,
        user_diff=user_diff,
        compiled_prompt=compiled_prompt,
        request_schema=output_schema,
        content_hash=_sha256(snapshot_payload),
        context_hash=context.content_hash,
        preview=preview,
    )


def _validate_bindings(
    bindings: tuple[ContextBinding, ...],
    allowed_sources: frozenset[str],
) -> None:
    keys = [binding.binding_key for binding in bindings]
    if len(keys) != len(set(keys)):
        raise PromptRuntimeError("CONTEXT_BINDING_DUPLICATE", "context binding keys must be unique")
    for binding in bindings:
        if binding.source not in allowed_sources:
            raise PromptRuntimeError(
                "CONTEXT_SOURCE_FORBIDDEN",
                f"context source is not registered: {binding.source}",
            )
        if binding.exposure not in {"full", "summary", "hidden"}:
            raise PromptRuntimeError(
                "CONTEXT_EXPOSURE_INVALID",
                f"context exposure is invalid: {binding.binding_key}",
            )
        if binding.max_items < 1 or binding.max_bytes < 1:
            raise PromptRuntimeError(
                "CONTEXT_LIMIT_INVALID",
                f"context limits must be positive: {binding.binding_key}",
            )


def _serialize_context_item(binding: ContextBinding, item: ContextItem) -> dict[str, Any]:
    if item.source != binding.source:
        raise PromptRuntimeError(
            "CONTEXT_SOURCE_MISMATCH",
            f"context item source does not match binding: {binding.binding_key}",
        )
    if not item.source_id.strip():
        raise PromptRuntimeError("CONTEXT_ITEM_INVALID", "context source_id cannot be empty")
    _canonical_json(item.content)
    return {
        "source_id": item.source_id,
        "source_version_id": item.source_version_id,
        "content": item.content,
    }


def _context_item_sort_key(item: ContextItem) -> tuple[str, str]:
    return item.source_id, item.source_version_id or ""


def _validate_prompt_input(
    *,
    template_key: str,
    template_version: str,
    platform_safety: str,
    sections: tuple[PromptSection, ...],
    provider_format: str,
    user_edit_mode: PromptEditMode,
    user_edit_max_chars: int,
    user_revision: str | None,
) -> None:
    if not template_key.strip() or not template_version.strip():
        raise PromptRuntimeError("PROMPT_TEMPLATE_REF_INVALID", "prompt template ref is required")
    if not platform_safety.strip() or not provider_format.strip():
        raise PromptRuntimeError("PROMPT_LOCKED_LAYER_MISSING", "locked prompt layers are required")
    if user_edit_mode != "replace_editable_layer" or not 1 <= user_edit_max_chars <= 100_000:
        raise PromptRuntimeError("PROMPT_EDIT_POLICY_INVALID", "prompt edit policy is invalid")
    keys = [section.section_key for section in sections]
    if not sections or len(keys) != len(set(keys)):
        raise PromptRuntimeError(
            "PROMPT_SECTION_INVALID",
            "prompt sections must be non-empty with unique keys",
        )
    if any(not section.content.strip() for section in sections):
        raise PromptRuntimeError("PROMPT_SECTION_INVALID", "prompt section content cannot be empty")
    if user_revision is not None and not user_revision.strip():
        raise PromptRuntimeError("PROMPT_REVISION_INVALID", "prompt revision cannot be empty")
    if user_revision is not None and len(user_revision) > user_edit_max_chars:
        raise PromptRuntimeError(
            "PROMPT_REVISION_TOO_LONG",
            "prompt revision exceeds the template edit limit",
        )
    if user_revision is not None and not any(section.editable for section in sections):
        raise PromptRuntimeError(
            "PROMPT_REVISION_FORBIDDEN",
            "prompt template has no editable business layer",
        )


def _effective_sections(
    sections: tuple[PromptSection, ...],
    user_revision: str | None,
) -> tuple[tuple[PromptSection, str], ...]:
    replacement_written = False
    result: list[tuple[PromptSection, str]] = []
    for section in sections:
        if not section.editable or user_revision is None:
            result.append((section, section.content))
            continue
        if replacement_written:
            continue
        result.append((section, user_revision))
        replacement_written = True
    return tuple(result)


def _teacher_prompt(
    sections: tuple[tuple[PromptSection, str], ...],
    context: AssembledContext,
) -> str:
    chunks = [content for section, content in sections if section.visible_to_teacher]
    for summary in _context_summaries(context):
        if summary["exposure"] != "full":
            continue
        binding = next(
            value for value in context.bindings if value["binding_key"] == summary["binding_key"]
        )
        items = cast(list[dict[str, Any]], binding["items"])
        chunks.append(_canonical_json_text({"context": [item["content"] for item in items]}))
    return "\n\n".join(chunks)


def _context_summaries(context: AssembledContext) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "binding_key": binding["binding_key"],
            "source": binding["source"],
            "exposure": binding["exposure"],
            "item_count": len(cast(list[object], binding["items"])),
            "content_hash": _sha256({"items": binding["items"]}),
        }
        for binding in context.bindings
    )


def _layer(layer: str, key: str, content: str, *, locked: bool) -> dict[str, Any]:
    return {"layer": layer, "key": key, "content": content, "locked": locked}


def _canonical_json(value: object) -> bytes:
    try:
        return _canonical_json_text(value).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PromptRuntimeError(
            "CONTEXT_VALUE_INVALID",
            "context and prompt values must be finite JSON",
        ) from exc


def _canonical_json_text(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()
