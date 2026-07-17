"""Build V1 content package items from compiler-normalized template fields."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from workflow.content_package import SCHEMA_FILES, canonical_json_sha256

ITEM_SUFFIXES = (
    ("input", "input_definition", "items/input-definition.json"),
    ("output", "content_definition", "items/content-definition.json"),
    ("prompt", "prompt_template", "items/prompt-template.json"),
    ("teacher_markdown", "projection_template", "items/teacher-markdown.json"),
    ("generate", "generation_template", "items/generation-template.json"),
)


def build_compiled_items(
    draft: Mapping[str, Any],
    profile: Mapping[str, Any],
    keys: Mapping[str, str],
    input_fields: list[dict[str, Any]],
    output_fields: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build the five #38 item kinds in stable dependency order."""

    metadata = {"domain": profile["domain"], "locale": profile["locale"]}
    ordered_items = (
        _build_input_item(draft, keys, metadata, input_fields),
        _build_output_item(draft, keys, metadata, output_fields),
        _build_prompt_item(draft, profile, keys, metadata),
        _build_projection_item(draft, profile, keys, metadata),
        _build_generation_item(draft, profile, keys, metadata),
    )
    return {cast(str, item["metadata"]["key"]): item for item in ordered_items}


def build_compiled_manifest(
    draft: Mapping[str, Any],
    profile: Mapping[str, Any],
    contracts_root: Path,
    keys: Mapping[str, str],
    items: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic manifest over the already-normalized items."""

    entries: list[dict[str, Any]] = []
    for suffix, kind, path in ITEM_SUFFIXES:
        schema = cast(
            dict[str, Any],
            json.loads((contracts_root / SCHEMA_FILES[kind]).read_text(encoding="utf-8")),
        )
        item = items[keys[suffix]]
        entries.append(
            {
                "item_key": keys[suffix],
                "kind": kind,
                "path": path,
                "schema_id": schema["$id"],
                "sha256": canonical_json_sha256(item),
            }
        )
    return {
        "format_version": "1.0",
        "package_key": profile["package_key"],
        "name": draft["title"],
        "semantic_version": profile["semantic_version"],
        "runtime_constraint": profile["runtime_constraint"],
        "change_summary": profile["change_summary"],
        "dependencies": [],
        "items": entries,
        "entrypoints": [keys["generate"]],
    }


def _build_input_item(
    draft: Mapping[str, Any],
    keys: Mapping[str, str],
    metadata: Mapping[str, Any],
    fields: list[dict[str, Any]],
) -> dict[str, Any]:
    title = cast(str, draft["title"])
    return _content_item(
        "input_definition",
        keys["input"],
        f"{title}输入",
        metadata,
        {"definition_key": keys["input"], "title": f"{title}输入", "fields": fields},
    )


def _build_output_item(
    draft: Mapping[str, Any],
    keys: Mapping[str, str],
    metadata: Mapping[str, Any],
    fields: list[dict[str, Any]],
) -> dict[str, Any]:
    title = cast(str, draft["title"])
    return _content_item(
        "content_definition",
        keys["output"],
        title,
        metadata,
        {
            "definition_key": keys["output"],
            "title": title,
            "definition_role": "artifact",
            "fields": fields,
        },
    )


def _build_prompt_item(
    draft: Mapping[str, Any],
    profile: Mapping[str, Any],
    keys: Mapping[str, str],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    title = cast(str, draft["title"])
    spec = {
        "template_key": keys["prompt"],
        "title": f"{title}生成指令",
        "model_capability": profile["model_capability"],
        "input_definition_ref": {"item_key": keys["input"], "kind": "input_definition"},
        "output_definition_ref": {
            "item_key": keys["output"],
            "kind": "content_definition",
        },
        "sections": _prompt_sections(profile),
        "context_bindings": list(profile["context_bindings"]),
        "user_edit_policy": dict(cast(Mapping[str, Any], profile["user_edit_policy"])),
    }
    return _content_item(
        "prompt_template",
        keys["prompt"],
        f"{title}生成指令",
        metadata,
        spec,
    )


def _prompt_sections(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "section_key": "role",
            "layer": "role",
            "content": profile["prompt_role"],
            "editable": False,
            "visible_to_teacher": True,
        },
        {
            "section_key": "task",
            "layer": "task",
            "content": profile["prompt_task"],
            "editable": True,
            "visible_to_teacher": True,
        },
        {
            "section_key": "method",
            "layer": "method",
            "content": "严格按照已确认的结构化字段生成。不得新增、删除或重命名字段。",
            "editable": False,
            "visible_to_teacher": True,
        },
    ]


def _build_projection_item(
    draft: Mapping[str, Any],
    profile: Mapping[str, Any],
    keys: Mapping[str, str],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    title = cast(str, draft["title"])
    return _content_item(
        "projection_template",
        keys["teacher_markdown"],
        f"{title} Markdown",
        metadata,
        _projection_spec(draft, profile, keys),
    )


def _projection_spec(
    draft: Mapping[str, Any],
    profile: Mapping[str, Any],
    keys: Mapping[str, str],
) -> dict[str, Any]:
    chunks = [f"# {draft['title']}"]
    variables: list[str] = []
    for section in cast(list[dict[str, Any]], draft["sections"]):
        if not section["visible"]:
            continue
        key = cast(str, section["section_key"])
        chunks.append(f"## {section['title']}\n\n{{{{{key}}}}}")
        variables.append(key)
    return {
        "projection_key": keys["teacher_markdown"],
        "title": f"{draft['title']} Markdown",
        "source_definition_ref": {
            "item_key": keys["output"],
            "kind": "content_definition",
        },
        "output_format": "markdown",
        "renderer_id": profile["renderer_id"],
        "template": "\n\n".join(chunks),
        "allowed_variables": variables,
        "teacher_visible": True,
    }


def _build_generation_item(
    draft: Mapping[str, Any],
    profile: Mapping[str, Any],
    keys: Mapping[str, str],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    title = cast(str, draft["title"])
    spec = {
        "template_key": keys["generate"],
        "title": f"生成{title}",
        "model_capability": profile["model_capability"],
        "input_definition_ref": {"item_key": keys["input"], "kind": "input_definition"},
        "prompt_template_ref": {"item_key": keys["prompt"], "kind": "prompt_template"},
        "output_definition_ref": {
            "item_key": keys["output"],
            "kind": "content_definition",
        },
        "projection_refs": [
            {
                "role": "teacher_view",
                "template_ref": {
                    "item_key": keys["teacher_markdown"],
                    "kind": "projection_template",
                },
            }
        ],
    }
    return _content_item(
        "generation_template",
        keys["generate"],
        f"生成{title}",
        metadata,
        spec,
    )


def _content_item(
    kind: str,
    key: str,
    name: str,
    common_metadata: Mapping[str, Any],
    spec: dict[str, Any],
) -> dict[str, Any]:
    return {
        "api_version": "shanhai.edu/v1",
        "kind": kind,
        "metadata": {"key": key, "name": name, **common_metadata},
        "spec": spec,
    }
