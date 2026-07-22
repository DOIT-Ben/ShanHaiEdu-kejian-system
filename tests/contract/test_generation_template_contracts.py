from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from workflow.content_package import (
    MAX_CONTENT_PACKAGE_JSON_BYTES,
    ContentPackageValidationError,
    canonical_json_sha256,
    validate_content_package,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
EXAMPLE_PACKAGE = CONTRACTS / "fixtures/generation-template-package"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def copy_example(tmp_path: Path) -> Path:
    target = tmp_path / "package"
    shutil.copytree(EXAMPLE_PACKAGE, target)
    return target


def update_item(
    package_root: Path,
    item_key: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    manifest_path = package_root / "manifest.json"
    manifest = load_json(manifest_path)
    entry = next(item for item in manifest["items"] if item["item_key"] == item_key)
    item_path = package_root / entry["path"]
    item = load_json(item_path)
    mutate(item)
    write_json(item_path, item)
    entry["sha256"] = canonical_json_sha256(item)
    write_json(manifest_path, manifest)


def assert_rejected(package_root: Path, code: str) -> None:
    with pytest.raises(ContentPackageValidationError) as caught:
        validate_content_package(package_root, contracts_root=CONTRACTS)
    assert caught.value.code == code


def test_example_package_is_valid_and_preserves_teacher_friendly_projections() -> None:
    package = validate_content_package(EXAMPLE_PACKAGE, contracts_root=CONTRACTS)

    assert len(package.items) == 11
    image_fields = {
        field["field_key"] for field in package.items["image_prompt.components"]["spec"]["fields"]
    }
    assert {
        "content",
        "composition",
        "palette",
        "texture",
        "lighting",
        "negative_constraints",
    }.issubset(image_fields)
    image_prompt = package.items["image_prompt.teacher_text"]["spec"]
    assert image_prompt["output_format"] == "prompt_text"
    assert "{{content}}" in image_prompt["template"]

    ppt_fields = {
        field["field_key"] for field in package.items["ppt_design.page"]["spec"]["fields"]
    }
    assert {
        "page_type",
        "teaching_goal",
        "visual_style",
        "background_policy",
        "layout",
        "editable_elements",
        "asset_requirements",
    } == ppt_fields
    assert package.items["ppt_design.teacher_markdown"]["spec"]["output_format"] == "markdown"


def test_prompt_append_edit_policy_is_rejected_by_the_package_contract(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)

    def mutate(item: dict[str, Any]) -> None:
        item["spec"]["user_edit_policy"]["mode"] = "append"

    update_item(package_root, "image_prompt.authoring", mutate)
    assert_rejected(package_root, "PACKAGE_ITEM_SPEC_INVALID")


def test_unknown_kind_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    manifest = load_json(package_root / "manifest.json")
    manifest["items"][0]["kind"] = "arbitrary_template"
    write_json(package_root / "manifest.json", manifest)
    assert_rejected(package_root, "PACKAGE_MANIFEST_INVALID")


def test_duplicate_item_key_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    manifest = load_json(package_root / "manifest.json")
    duplicate = dict(manifest["items"][1])
    duplicate["path"] = manifest["items"][0]["path"]
    duplicate["item_key"] = manifest["items"][0]["item_key"]
    manifest["items"].append(duplicate)
    write_json(package_root / "manifest.json", manifest)
    assert_rejected(package_root, "PACKAGE_DUPLICATE_ITEM_KEY")


def test_manifest_and_item_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    update_item(
        package_root,
        "image_prompt.input",
        lambda item: item["metadata"].update({"key": "image_prompt.other"}),
    )
    assert_rejected(package_root, "PACKAGE_ITEM_IDENTITY_MISMATCH")


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    manifest = load_json(package_root / "manifest.json")
    manifest["items"][0]["path"] = "../outside.json"
    write_json(package_root / "manifest.json", manifest)
    assert_rejected(package_root, "PACKAGE_MANIFEST_INVALID")


def test_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    manifest = load_json(package_root / "manifest.json")
    manifest["items"][0]["sha256"] = "f" * 64
    write_json(package_root / "manifest.json", manifest)
    assert_rejected(package_root, "PACKAGE_HASH_MISMATCH")


def test_schema_id_mismatch_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    manifest = load_json(package_root / "manifest.json")
    manifest["items"][0]["schema_id"] = manifest["items"][1]["schema_id"]
    write_json(package_root / "manifest.json", manifest)
    assert_rejected(package_root, "PACKAGE_SCHEMA_ID_MISMATCH")


def test_entrypoint_must_reference_generation_template(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    manifest = load_json(package_root / "manifest.json")
    manifest["entrypoints"] = ["image_prompt.input"]
    write_json(package_root / "manifest.json", manifest)
    assert_rejected(package_root, "PACKAGE_ENTRYPOINT_INVALID")


def test_unresolved_reference_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)

    def mutate(item: dict[str, Any]) -> None:
        item["spec"]["output_definition_ref"]["item_key"] = "image_prompt.missing"

    update_item(package_root, "image_prompt.generate", mutate)
    assert_rejected(package_root, "PACKAGE_REFERENCE_UNRESOLVED")


def test_reference_kind_mismatch_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)

    def mutate(item: dict[str, Any]) -> None:
        item["spec"]["output_definition_ref"]["item_key"] = "image_prompt.authoring"

    update_item(package_root, "image_prompt.generate", mutate)
    assert_rejected(package_root, "PACKAGE_REFERENCE_KIND_MISMATCH")


def test_unregistered_context_source_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)

    def mutate(item: dict[str, Any]) -> None:
        item["spec"]["context_bindings"][0]["source"] = "database.any_table"

    update_item(package_root, "image_prompt.authoring", mutate)
    assert_rejected(package_root, "PACKAGE_CONTEXT_SOURCE_FORBIDDEN")


def test_duplicate_logical_field_key_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)

    def mutate(item: dict[str, Any]) -> None:
        item["spec"]["fields"].append(dict(item["spec"]["fields"][0]))

    update_item(package_root, "image_prompt.input", mutate)
    assert_rejected(package_root, "PACKAGE_DUPLICATE_LOGICAL_KEY")


@pytest.mark.parametrize("mutation", ["condition", "target", "overlap", "cross_overlap"])
def test_invalid_conditional_input_requirement_is_rejected(tmp_path: Path, mutation: str) -> None:
    package_root = copy_example(tmp_path)

    def mutate(item: dict[str, Any]) -> None:
        field_keys = [field["field_key"] for field in item["spec"]["fields"]]
        condition_key, target_key = field_keys[:2]
        requirement = {
            "when": {"field_key": condition_key, "equals": "enabled"},
            "required_fields": [target_key],
        }
        requirements = [requirement]
        if mutation == "condition":
            requirement["when"]["field_key"] = "missing.condition"
        elif mutation == "target":
            requirement["required_fields"] = ["missing.target"]
        elif mutation == "overlap":
            requirement["forbidden_fields"] = [target_key]
        else:
            requirements.append(
                {
                    "when": {"field_key": condition_key, "equals": "enabled"},
                    "forbidden_fields": [target_key],
                }
            )
        item["spec"]["conditional_requirements"] = requirements

    update_item(package_root, "image_prompt.input", mutate)
    assert_rejected(package_root, "PACKAGE_INPUT_CONDITION_INVALID")


def test_projection_template_cannot_use_undeclared_variable(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)

    def mutate(item: dict[str, Any]) -> None:
        item["spec"]["template"] += "{{provider_secret}}"

    update_item(package_root, "image_prompt.teacher_text", mutate)
    assert_rejected(package_root, "PACKAGE_PROJECTION_VARIABLE_FORBIDDEN")


def test_projection_allowlist_must_come_from_source_definition(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)

    def mutate(item: dict[str, Any]) -> None:
        item["spec"]["allowed_variables"].append("provider_secret")

    update_item(package_root, "image_prompt.teacher_text", mutate)
    assert_rejected(package_root, "PACKAGE_PROJECTION_VARIABLE_FORBIDDEN")


def test_invalid_utf8_uses_stable_package_error(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    (package_root / "manifest.json").write_bytes(b"\xff\xfe")
    assert_rejected(package_root, "PACKAGE_JSON_INVALID")


def test_oversized_json_is_rejected_before_parsing(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    (package_root / "manifest.json").write_bytes(b"x" * (MAX_CONTENT_PACKAGE_JSON_BYTES + 1))
    assert_rejected(package_root, "PACKAGE_JSON_TOO_LARGE")


def test_windows_device_path_is_rejected(tmp_path: Path) -> None:
    package_root = copy_example(tmp_path)
    manifest = load_json(package_root / "manifest.json")
    manifest["items"][0]["path"] = "items/CON.json"
    write_json(package_root / "manifest.json", manifest)
    assert_rejected(package_root, "PACKAGE_PATH_INVALID")
