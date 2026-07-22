"""Build a deterministic V1 content package from a compact built-in source."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from workflow.content_package import canonical_json_sha256, validate_content_package

SCHEMA_FILES = {
    "input_definition": "input-definition.schema.json",
    "content_definition": "content-definition.schema.json",
    "style_preset": "style-preset.schema.json",
    "prompt_template": "prompt-template.schema.json",
    "projection_template": "projection-template.schema.json",
    "generation_template": "generation-template.schema.json",
}


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return cast(dict[str, Any], value)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _item(kind: str, key: str, title: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "api_version": "shanhai.edu/v1",
        "kind": kind,
        "metadata": {
            "key": key,
            "name": title,
            "domain": "primary_math",
            "locale": "zh-CN",
        },
        "spec": dict(spec),
    }


def _safe_filename(key: str, suffix: str) -> str:
    return f"{key.replace('.', '-').replace('_', '-')}-{suffix}.json"


def _schema_id(contracts_root: Path, kind: str) -> str:
    schema = _load_object(contracts_root / SCHEMA_FILES[kind])
    return cast(str, schema["$id"])


def _append_item(
    *,
    items: list[dict[str, Any]],
    manifest_items: list[dict[str, Any]],
    item: dict[str, Any],
    filename: str,
    contracts_root: Path,
) -> None:
    kind = cast(str, item["kind"])
    key = cast(str, item["metadata"]["key"])
    items.append({"path": f"items/{filename}", "value": item})
    manifest_items.append(
        {
            "item_key": key,
            "kind": kind,
            "path": f"items/{filename}",
            "schema_id": _schema_id(contracts_root, kind),
            "sha256": canonical_json_sha256(item),
        }
    )


def _build_node_items(
    node: Mapping[str, Any],
    *,
    contracts_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    template_key = cast(str, node["template_key"])
    title = cast(str, node["title"])
    description = cast(str, node["description"])
    capability = cast(str, node["model_capability"])
    input_key = f"{template_key}.input"
    output_key = f"{template_key}.output"
    prompt_key = f"{template_key}.prompt"
    projection_key = f"{template_key}.projection"
    input_ref = {"item_key": input_key, "kind": "input_definition"}
    output_ref = {"item_key": output_key, "kind": "content_definition"}
    prompt_ref = {"item_key": prompt_key, "kind": "prompt_template"}
    projection_ref = {"item_key": projection_key, "kind": "projection_template"}

    input_source = cast(Mapping[str, Any], node["input"])
    output_source = cast(Mapping[str, Any], node["output"])
    prompt_source = cast(Mapping[str, Any], node["prompt"])
    projection_source = cast(Mapping[str, Any], node["projection"])
    input_spec = {
        "definition_key": input_key,
        "title": f"{title}输入",
        "description": input_source["description"],
        "fields": input_source["fields"],
    }
    if "conditional_requirements" in input_source:
        input_spec["conditional_requirements"] = input_source["conditional_requirements"]
    prompt_sections = [
        {
            "section_key": "role",
            "layer": "role",
            "content": prompt_source["role"],
            "editable": False,
            "visible_to_teacher": True,
        },
        {
            "section_key": "task",
            "layer": "task",
            "content": prompt_source["task"],
            "editable": True,
            "visible_to_teacher": True,
        },
        {
            "section_key": "method",
            "layer": "method",
            "content": prompt_source["method"],
            "editable": False,
            "visible_to_teacher": False,
        },
        {
            "section_key": "quality_gate",
            "layer": "quality_gate",
            "content": prompt_source["quality_gate"],
            "editable": False,
            "visible_to_teacher": False,
        },
    ]

    generated_items = [
        _item(
            "input_definition",
            input_key,
            f"{title}输入",
            input_spec,
        ),
        _item(
            "content_definition",
            output_key,
            f"{title}输出",
            {
                "definition_key": output_key,
                "title": f"{title}输出",
                "description": output_source["description"],
                "definition_role": output_source["definition_role"],
                "fields": output_source["fields"],
            },
        ),
        _item(
            "prompt_template",
            prompt_key,
            f"{title}业务Prompt",
            {
                "template_key": prompt_key,
                "title": f"{title}业务Prompt",
                "description": description,
                "model_capability": capability,
                "input_definition_ref": input_ref,
                "output_definition_ref": output_ref,
                "sections": prompt_sections,
                "context_bindings": prompt_source["context_bindings"],
                "user_edit_policy": {
                    "mode": "replace_editable_layer",
                    "max_chars": prompt_source["max_chars"],
                },
            },
        ),
        _item(
            "projection_template",
            projection_key,
            f"{title}教师投影",
            {
                "projection_key": projection_key,
                "title": f"{title}教师投影",
                "source_definition_ref": output_ref,
                "output_format": projection_source["output_format"],
                "renderer_id": projection_source["renderer_id"],
                "template": projection_source["template"],
                "allowed_variables": projection_source["allowed_variables"],
                "teacher_visible": projection_source.get("teacher_visible", True),
            },
        ),
        _item(
            "generation_template",
            template_key,
            title,
            {
                "template_key": template_key,
                "title": title,
                "description": description,
                "model_capability": capability,
                "input_definition_ref": input_ref,
                "prompt_template_ref": prompt_ref,
                "output_definition_ref": output_ref,
                "style_preset_refs": [
                    {"item_key": key, "kind": "style_preset"}
                    for key in cast(list[str], node.get("style_preset_refs", []))
                ],
                "projection_refs": [
                    {"role": role, "template_ref": projection_ref}
                    for role in cast(list[str], projection_source["roles"])
                ],
            },
        ),
    ]

    files: list[dict[str, Any]] = []
    manifest_items: list[dict[str, Any]] = []
    suffixes = ["input", "output", "prompt", "projection", "generation"]
    for item, suffix in zip(generated_items, suffixes, strict=True):
        _append_item(
            items=files,
            manifest_items=manifest_items,
            item=item,
            filename=_safe_filename(template_key, suffix),
            contracts_root=contracts_root,
        )
    return files, manifest_items


def _build_deterministic_output_item(output: Mapping[str, Any]) -> dict[str, Any]:
    output_key = cast(str, output["output_key"])
    return _item(
        "content_definition",
        output_key,
        cast(str, output["title"]),
        {
            "definition_key": output_key,
            "title": output["title"],
            "description": output["description"],
            "definition_role": output["definition_role"],
            "fields": output["fields"],
        },
    )


def build_package(source_path: Path, output_root: Path, *, contracts_root: Path) -> None:
    """Build and validate a deterministic package into an empty output directory."""

    source = _load_object(source_path)
    source_schema = _load_object(contracts_root / "builtin-generation-source.schema.json")
    Draft202012Validator.check_schema(source_schema)
    source_validator = cast(
        Any,
        Draft202012Validator(
            source_schema,
            format_checker=FormatChecker(),
        ),
    )
    source_validator.validate(source)

    if output_root.exists() and any(output_root.iterdir()):
        raise ValueError(f"output directory must be empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    package = cast(Mapping[str, Any], source["package"])
    style_keys: set[str] = set()
    node_keys: set[str] = set()
    content_definition_keys: set[str] = set()
    files: list[dict[str, Any]] = []
    manifest_items: list[dict[str, Any]] = []

    for style in cast(list[dict[str, Any]], source["styles"]):
        key = cast(str, style["preset_key"])
        if key in style_keys:
            raise ValueError(f"duplicate style preset: {key}")
        style_keys.add(key)
        item = _item("style_preset", key, cast(str, style["title"]), style)
        _append_item(
            items=files,
            manifest_items=manifest_items,
            item=item,
            filename=_safe_filename(key, "style"),
            contracts_root=contracts_root,
        )

    for artifact in cast(list[dict[str, Any]], source["artifacts"]):
        key = cast(str, artifact["definition_key"])
        if key in node_keys:
            raise ValueError(f"duplicate content item: {key}")
        node_keys.add(key)
        item = _item(
            "content_definition",
            key,
            cast(str, artifact["title"]),
            {
                "definition_key": key,
                "title": artifact["title"],
                "description": artifact["description"],
                "definition_role": "artifact",
                "fields": artifact["fields"],
            },
        )
        _append_item(
            items=files,
            manifest_items=manifest_items,
            item=item,
            filename=_safe_filename(key, "output"),
            contracts_root=contracts_root,
        )

    entrypoints: list[str] = []
    for node in cast(list[dict[str, Any]], source["nodes"]):
        key = cast(str, node["template_key"])
        if key in node_keys:
            raise ValueError(f"duplicate generation template: {key}")
        node_keys.add(key)
        output_key = f"{key}.output"
        if output_key in content_definition_keys:
            raise ValueError(f"duplicate content definition: {output_key}")
        content_definition_keys.add(output_key)
        unknown_styles = set(cast(list[str], node.get("style_preset_refs", []))) - style_keys
        if unknown_styles:
            raise ValueError(f"{key} references unknown styles: {sorted(unknown_styles)}")
        node_files, node_manifest_items = _build_node_items(
            node,
            contracts_root=contracts_root,
        )
        files.extend(node_files)
        manifest_items.extend(node_manifest_items)
        entrypoints.append(key)

    for output in cast(list[dict[str, Any]], source.get("deterministic_outputs", [])):
        output_key = cast(str, output["output_key"])
        if output_key in content_definition_keys:
            raise ValueError(f"duplicate content definition: {output_key}")
        content_definition_keys.add(output_key)
        item = _build_deterministic_output_item(output)
        base_key = output_key.removesuffix(".output")
        _append_item(
            items=files,
            manifest_items=manifest_items,
            item=item,
            filename=_safe_filename(base_key, "output"),
            contracts_root=contracts_root,
        )

    for file in files:
        _write_json(output_root / cast(str, file["path"]), cast(dict[str, Any], file["value"]))
    manifest = {
        "format_version": "1.0",
        "package_key": package["package_key"],
        "name": package["name"],
        "semantic_version": package["semantic_version"],
        "runtime_constraint": package["runtime_constraint"],
        "change_summary": package["change_summary"],
        "dependencies": [],
        "items": manifest_items,
        "entrypoints": entrypoints,
    }
    _write_json(output_root / "manifest.json", manifest)
    validate_content_package(output_root, contracts_root=contracts_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--contracts-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "contracts",
    )
    args = parser.parse_args()
    build_package(args.source, args.output, contracts_root=args.contracts_root)
    print(f"built {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
