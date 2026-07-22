from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Any
from uuid import uuid4

import pytest
from alembic.config import Config
from jsonschema import Draft202012Validator
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from apps.api.artifacts.validation import ArtifactValidation
from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackage,
    ContentPackageItemVersion,
    ContentPackageVersion,
    ContentRelease,
    ContentReleaseItem,
    RuntimeDefaultVersion,
)
from apps.api.content_runtime.package_source import (
    BuiltinCoursewareReleaseSource,
    ContentPublicationConflict,
    _validate_catalog_content_definitions,
    load_builtin_courseware_release,
)
from apps.api.content_runtime.publication_service import ContentReleasePublisher, PublicationResult
from apps.api.content_runtime.registry import BUILTIN_RUNTIME_DEFAULTS
from apps.api.content_runtime.service import resolve_runtime_defaults
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.models import SYSTEM_PRINCIPAL_ID
from apps.api.ids import new_uuid7
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.models import WorkflowDefinitionVersion
from tests.fakes.identity import seed_test_actor
from workflow.content_package import canonical_json_sha256
from workflow.definition import WorkflowDefinitionError
from workflow.node_generation_binding import canonical_catalog_json
from workflow.registry import (
    BUILTIN_WORKFLOW_REGISTRY,
    LEGACY_WORKFLOW_CATALOG_API_VERSION,
)

ROOT = Path(__file__).resolve().parents[2]
LEGACY_RELEASE_FIXTURE_ROOT = ROOT / "tests/fixtures/content_runtime/primary_math_courseware_1_0"
LEGACY_PACKAGE_CHECKSUM = "894771a7472723cb70a4586a7905af480e04f5baee636351a4cc0597c6c9712f"
LEGACY_WORKFLOW_CHECKSUM = "268f503e9e7e455aab936e885d1c67b1934384d45c2ef0e4d0399683e579e7ea"
PREVIOUS_PACKAGE_CHECKSUM = "84bfc3e5aac3a94b877513ca451c72b4ac9c5b516bc773abe3d90715a6393023"
PREVIOUS_WORKFLOW_CHECKSUM = "8249b49fc0d5ee03d9a598851a15f8effec9ed89a2fb66b7abd863483529e623"
RELEASE_1_2_PACKAGE_CHECKSUM = "767f6883f8a881c793f8f03ea39fe1ae83ab0f80073e7cc4f51a51bf7ed74393"
RELEASE_1_2_WORKFLOW_CHECKSUM = "9e988bcaf97b063dd4ad11e28d6e4e687c411c549628909f12f5cb1be20204c8"
RELEASE_1_2_CHANGE_SUMMARY = (
    "前向修正导入方案返修的同一Artifact supersedes血缘，并声明通用workflow gate批准终态；"  # noqa: RUF001
    "旧Release与既有项目绑定保持不变。"
)
RELEASE_1_3_ITEM_KEYS = frozenset({"ppt.pages.assemble.output", "pptx.export.output"})
PREVIOUS_INTRO_SINGLE_ANCHOR = {
    "key": "validator.intro.single_anchor",
    "semantic_version": "1.0.0",
    "implementation_digest": "c32be2ad3444760ff6d7454d7bc3e7a9a3518e223931d2792fabf2980e8a36dd",
}
PREVIOUS_CHANGE_SUMMARY = (
    "发布显式48节点拓扑、22个模型节点输出持久化、质量报告/人工门禁声明和受限"
    "Artifact/CreationPackage投影合同；固定导入方案一套/九套、exact来源、独立批准和选择语义。"  # noqa: RUF001
)


@pytest.fixture(scope="module")
def builtin_courseware_source() -> BuiltinCoursewareReleaseSource:
    return load_builtin_courseware_release(ROOT)


def package_node(catalog: dict[str, Any], node_key: str) -> dict[str, Any]:
    nodes = catalog["nodes"]
    assert isinstance(nodes, list)
    node = next(item for item in nodes if item["node_key"] == node_key)
    assert isinstance(node, dict)
    return node


def replace_validator_ref(
    refs: list[dict[str, Any]],
    replacement: dict[str, str],
) -> None:
    index = next(index for index, ref in enumerate(refs) if ref.get("key") == replacement["key"])
    refs[index] = {**refs[index], **replacement}


def validate_catalog_source(
    source: BuiltinCoursewareReleaseSource,
    catalog: dict[str, Any],
    *,
    items: dict[str, dict[str, Any]] | None = None,
) -> None:
    _validate_catalog_content_definitions(
        catalog,
        source.items if items is None else items,
        source.manifest_entries,
    )


def test_creation_package_mappings_match_output_definitions(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    package_nodes = [
        node
        for node in catalog["nodes"]
        if node.get("output_persistence", {}).get("creation_package") is not None
    ]

    assert {node["node_key"] for node in package_nodes} == {
        "ppt.body_asset_prompts.generate",
        "video.asset_prompts.generate",
    }
    assert all(
        node["output_persistence"]["creation_package"]["item_mapping"]["output_spec"]
        == {"source": "item", "pointer": ""}
        for node in package_nodes
    )
    validate_catalog_source(builtin_courseware_source, catalog)


@pytest.mark.parametrize(
    ("pointer", "message"),
    [
        (
            "/not_declared",
            "creation package items_pointer does not resolve to a required object array: "
            "ppt.body_asset_prompts.generate /not_declared",
        ),
        (
            "/body_package_key",
            "creation package items_pointer does not resolve to a required object array: "
            "ppt.body_asset_prompts.generate /body_package_key",
        ),
    ],
)
def test_creation_package_items_pointer_must_resolve_to_an_object_array(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    pointer: str,
    message: str,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    node["output_persistence"]["creation_package"]["items_pointer"] = pointer

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog)

    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("bound", "unsafe_value"),
    [
        ("min_items", None),
        ("min_items", 0),
        ("min_items", 101),
        ("max_items", None),
        ("max_items", 0),
        ("max_items", 101),
    ],
)
def test_creation_package_items_array_must_declare_safe_bounds(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    bound: str,
    unsafe_value: int | None,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    items = deepcopy(builtin_courseware_source.items)
    output = items["ppt.body_asset_prompts.generate.output"]
    body_items = next(
        field for field in output["spec"]["fields"] if field["field_key"] == "body_asset_items"
    )
    if unsafe_value is None:
        body_items.pop(bound, None)
    else:
        body_items[bound] = unsafe_value

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog, items=items)

    assert str(caught.value) == (
        "creation package items array bounds are unsafe: "
        "ppt.body_asset_prompts.generate /body_asset_items"
    )


@pytest.mark.parametrize(
    ("source_kind", "pointer"),
    [
        ("item", "/not_declared"),
        ("item", "/body_package_key"),
        ("output", "/not_declared"),
    ],
)
def test_creation_package_mapping_pointer_must_match_its_source_schema(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    source_kind: str,
    pointer: str,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    node["output_persistence"]["creation_package"]["item_mapping"]["title"] = {
        "source": source_kind,
        "pointer": pointer,
    }

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog)

    assert str(caught.value) == (
        "creation package item_mapping pointer does not resolve to a required output field: "
        f"ppt.body_asset_prompts.generate title {source_kind} {pointer}"
    )


@pytest.mark.parametrize("optional_field", ["items", "item_key"])
def test_creation_package_projection_fields_must_be_required_by_the_output_definition(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    optional_field: str,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    items = deepcopy(builtin_courseware_source.items)
    output = items["ppt.body_asset_prompts.generate.output"]
    body_items = next(
        field for field in output["spec"]["fields"] if field["field_key"] == "body_asset_items"
    )
    target = (
        body_items
        if optional_field == "items"
        else next(
            field for field in body_items["children"] if field["field_key"] == "body_item_key"
        )
    )
    target["required"] = False

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog, items=items)

    if optional_field == "items":
        assert str(caught.value) == (
            "creation package items_pointer does not resolve to a required object array: "
            "ppt.body_asset_prompts.generate /body_asset_items"
        )
    else:
        assert str(caught.value) == (
            "creation package item_mapping pointer does not resolve to a required output field: "
            "ppt.body_asset_prompts.generate item_key item /body_item_key"
        )


@pytest.mark.parametrize(
    ("mapping_name", "source_kind", "pointer"),
    [
        ("item_key", "item", "/body_negative_constraints"),
        ("position", "item", "/body_item_key"),
        ("title", "item", "/body_negative_constraints"),
        ("title", "output", "/body_asset_items"),
        ("business_prompt", "item", "/body_negative_constraints"),
        ("output_spec", "item", "/body_prompt_text"),
        ("target_slot", "item", "/body_negative_constraints"),
        ("consistency_key", "item", "/body_negative_constraints"),
    ],
)
def test_creation_package_mapping_pointer_must_have_a_compatible_schema_type(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    mapping_name: str,
    source_kind: str,
    pointer: str,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    node["output_persistence"]["creation_package"]["item_mapping"][mapping_name] = {
        "source": source_kind,
        "pointer": pointer,
    }

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog)

    assert str(caught.value) == (
        "creation package item_mapping type is incompatible with the output definition: "
        f"ppt.body_asset_prompts.generate {mapping_name} {source_kind} {pointer}"
    )


@pytest.mark.parametrize(
    ("mapping_name", "field_key", "operator", "unsafe_value"),
    [
        ("item_key", "body_item_key", "min_length", None),
        ("item_key", "body_item_key", "min_length", 0),
        ("item_key", "body_item_key", "max_length", None),
        ("item_key", "body_item_key", "max_length", 0),
        ("item_key", "body_item_key", "max_length", 161),
        ("business_prompt", "body_prompt_text", "max_length", 50_001),
        ("consistency_key", "body_consistency_key", "max_length", 161),
        ("target_slot", "body_target_slot", "max_length", 161),
    ],
)
def test_creation_package_string_mappings_must_declare_safe_length_bounds(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    mapping_name: str,
    field_key: str,
    operator: str,
    unsafe_value: int | None,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    items = deepcopy(builtin_courseware_source.items)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    output = items["ppt.body_asset_prompts.generate.output"]
    body_items = next(
        field for field in output["spec"]["fields"] if field["field_key"] == "body_asset_items"
    )
    target = next(field for field in body_items["children"] if field["field_key"] == field_key)
    rules = [rule for rule in target.get("validation_rules", []) if operator not in rule]
    if unsafe_value is not None:
        rules.append({operator: unsafe_value})
    target["validation_rules"] = rules

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog, items=items)

    pointer = node["output_persistence"]["creation_package"]["item_mapping"][mapping_name][
        "pointer"
    ]
    assert str(caught.value) == (
        "creation package string mapping bounds are unsafe: "
        f"ppt.body_asset_prompts.generate {mapping_name} item {pointer}"
    )


def test_creation_package_title_mapping_respects_its_runtime_length_limit(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    items = deepcopy(builtin_courseware_source.items)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    mapping = node["output_persistence"]["creation_package"]["item_mapping"]
    mapping["item_key"] = {"source": "constant", "value": "fixed-item"}
    output = items["ppt.body_asset_prompts.generate.output"]
    body_items = next(
        field for field in output["spec"]["fields"] if field["field_key"] == "body_asset_items"
    )
    item_key = next(
        field for field in body_items["children"] if field["field_key"] == "body_item_key"
    )
    item_key["validation_rules"] = [
        {"min_length": 1},
        {"max_length": 256},
    ]

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog, items=items)

    assert str(caught.value) == (
        "creation package string mapping bounds are unsafe: "
        "ppt.body_asset_prompts.generate title item /body_item_key"
    )


@pytest.mark.parametrize("pattern", [None, r"^[a-z0-9._-]+$"])
def test_creation_package_target_slot_mapping_requires_the_semantic_pattern(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    pattern: str | None,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    items = deepcopy(builtin_courseware_source.items)
    output = items["ppt.body_asset_prompts.generate.output"]
    body_items = next(
        field for field in output["spec"]["fields"] if field["field_key"] == "body_asset_items"
    )
    target_slot = next(
        field for field in body_items["children"] if field["field_key"] == "body_target_slot"
    )
    rules = [rule for rule in target_slot.get("validation_rules", []) if "pattern" not in rule]
    if pattern is not None:
        rules.append({"pattern": pattern})
    target_slot["validation_rules"] = rules

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog, items=items)

    assert str(caught.value) == (
        "creation package target_slot mapping lacks the required semantic pattern: "
        "ppt.body_asset_prompts.generate item /body_target_slot"
    )


@pytest.mark.parametrize(
    ("mapping_name", "projection", "location"),
    [
        ("title", {"source": "constant", "value": {}}, "<constant>"),
        (
            "title",
            {"source": "intrinsic", "name": "item_position"},
            "item_position",
        ),
        (
            "item_key",
            {"source": "runtime", "pointer": "/reference_assets"},
            "/reference_assets",
        ),
    ],
)
def test_creation_package_non_field_projection_must_have_a_compatible_type(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    mapping_name: str,
    projection: dict[str, Any],
    location: str,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    node["output_persistence"]["creation_package"]["item_mapping"][mapping_name] = projection

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog)

    assert str(caught.value) == (
        "creation package item_mapping type is incompatible with the output definition: "
        f"ppt.body_asset_prompts.generate {mapping_name} {projection['source']} {location}"
    )


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize(
    ("mapping_name", "value"),
    [
        ("item_key", ""),
        ("item_key", " " * 3),
        ("item_key", "a" * 161),
        ("title", "a" * 256),
        ("business_prompt", "a" * 50_001),
        ("consistency_key", "a" * 161),
    ],
    ids=(
        "empty-item-key",
        "blank-item-key",
        "long-item-key",
        "long-title",
        "long-business-prompt",
        "long-consistency-key",
    ),
)
def test_creation_package_constant_strings_must_fit_runtime_bounds(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    mapping_name: str,
    value: str,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    node["output_persistence"]["creation_package"]["item_mapping"][mapping_name] = {
        "source": "constant",
        "value": value,
    }

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog)

    assert str(caught.value) == (
        "creation package string mapping bounds are unsafe: "
        f"ppt.body_asset_prompts.generate {mapping_name} constant <constant>"
    )


@pytest.mark.parametrize("value", ["PPT.page-01.main-visual", "ppt..main-visual"])
def test_creation_package_constant_target_slot_must_be_semantic(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    value: str,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    node["output_persistence"]["creation_package"]["item_mapping"]["target_slot"] = {
        "source": "constant",
        "value": value,
    }

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog)

    assert str(caught.value) == (
        "creation package target_slot mapping lacks the required semantic pattern: "
        "ppt.body_asset_prompts.generate constant <constant>"
    )


@pytest.mark.parametrize("value", [0, 101])
def test_creation_package_constant_position_must_fit_package_bounds(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
    value: int,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    node["output_persistence"]["creation_package"]["item_mapping"]["position"] = {
        "source": "constant",
        "value": value,
    }

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog)

    assert str(caught.value) == (
        "creation package constant position is outside package bounds: "
        f"ppt.body_asset_prompts.generate {value}"
    )


def test_creation_package_runtime_string_mapping_requires_static_bounds(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    node["output_persistence"]["creation_package"]["item_mapping"]["title"] = {
        "source": "runtime",
        "pointer": "/lesson_key",
    }

    with pytest.raises(ContentPublicationConflict) as caught:
        validate_catalog_source(builtin_courseware_source, catalog)

    assert str(caught.value) == (
        "creation package string mapping bounds are unsafe: "
        "ppt.body_asset_prompts.generate title runtime /lesson_key"
    )


def test_creation_package_non_field_sources_and_valid_output_pointer_are_not_rejected(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    catalog = deepcopy(builtin_courseware_source.workflow_catalog)
    node = package_node(catalog, "ppt.body_asset_prompts.generate")
    mapping = node["output_persistence"]["creation_package"]["item_mapping"]
    mapping["title"] = {
        "source": "output",
        "pointer": "/body_asset_items/0/body_item_key",
    }
    mapping["reference_assets"] = {"source": "runtime", "pointer": "/reference_assets"}

    validate_catalog_source(builtin_courseware_source, catalog)


def legacy_courseware_release(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    manifest = load_json_object(LEGACY_RELEASE_FIXTURE_ROOT / "manifest.json")
    catalog = load_json_object(LEGACY_RELEASE_FIXTURE_ROOT / "workflow.json")
    entries = {
        entry["item_key"]: entry
        for entry in manifest["items"]
        if isinstance(entry, dict) and isinstance(entry.get("item_key"), str)
    }
    items = {item_key: deepcopy(source.items[item_key]) for item_key in entries}
    for entry in entries.values():
        fixture_path = LEGACY_RELEASE_FIXTURE_ROOT / entry["path"]
        if fixture_path.exists():
            items[entry["item_key"]] = load_json_object(fixture_path)
    if set(items) != set(entries):
        raise AssertionError("legacy package item inventory differs from the published snapshot")
    for item_key, entry in entries.items():
        if canonical_json_sha256(items[item_key]) != entry["sha256"]:
            raise AssertionError(f"legacy package item drifted: {item_key}")
    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if package_checksum != LEGACY_PACKAGE_CHECKSUM or workflow_checksum != LEGACY_WORKFLOW_CHECKSUM:
        raise AssertionError("legacy release checksum differs from the published snapshot")
    return replace(
        source,
        manifest=manifest,
        items=items,
        manifest_entries=entries,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def previous_courseware_release(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    release_1_2 = release_1_2_courseware_release(source)
    manifest = deepcopy(release_1_2.manifest)
    manifest["semantic_version"] = "1.1.0"
    manifest["change_summary"] = PREVIOUS_CHANGE_SUMMARY
    catalog = deepcopy(release_1_2.workflow_catalog)
    catalog["semantic_version"] = "1.1.0"
    intro = package_node(catalog, "intro.generate_options")
    persistence = intro["output_persistence"]
    relation = next(
        item
        for item in persistence["artifact"]["relations"]
        if item["source_binding"] == "artifact:intro_option_set_source"
    )
    relation["relation_type"] = "derives_from"
    relation["impact_scope"] = {
        "mode": "keyed",
        "selector": "lesson_key",
        "keys": {"source": "runtime", "pointer": "/lesson_key"},
    }
    persistence.pop("approval_completion")
    validate = package_node(catalog, "intro.validate")
    validate["input_contract_refs"] = ["artifact:intro_option_set"]
    report = validate["quality_report_persistence"]
    report.pop("supporting_input_refs")
    replace_validator_ref(validate["validator_refs"], PREVIOUS_INTRO_SINGLE_ANCHOR)
    replace_validator_ref(report["validator_refs"], PREVIOUS_INTRO_SINGLE_ANCHOR)
    replace_validator_ref(catalog["validator_descriptors"], PREVIOUS_INTRO_SINGLE_ANCHOR)
    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if (
        package_checksum != PREVIOUS_PACKAGE_CHECKSUM
        or workflow_checksum != PREVIOUS_WORKFLOW_CHECKSUM
    ):
        raise AssertionError("1.1.0 release checksum differs from the published snapshot")
    return replace(
        release_1_2,
        manifest=manifest,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def release_1_2_courseware_release(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    manifest = deepcopy(source.manifest)
    manifest["semantic_version"] = "1.2.0"
    manifest["change_summary"] = RELEASE_1_2_CHANGE_SUMMARY
    manifest["items"] = [
        entry for entry in manifest["items"] if entry["item_key"] not in RELEASE_1_3_ITEM_KEYS
    ]
    entries = {entry["item_key"]: entry for entry in manifest["items"]}
    items = {item_key: deepcopy(source.items[item_key]) for item_key in entries}

    catalog = deepcopy(source.workflow_catalog)
    catalog["semantic_version"] = "1.2.0"
    for node_key in (
        "lesson.division.generate",
        "lesson_plan.generate",
        "intro.generate_options",
    ):
        package_node(catalog, node_key)["output_persistence"].pop("quality_source_binding")
    package_node(catalog, "ppt.pages.assemble").pop("output_persistence")
    package_node(catalog, "pptx.export").pop("output_persistence")

    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if (
        package_checksum != RELEASE_1_2_PACKAGE_CHECKSUM
        or workflow_checksum != RELEASE_1_2_WORKFLOW_CHECKSUM
    ):
        raise AssertionError("1.2.0 release checksum differs from the published snapshot")
    return replace(
        source,
        manifest=manifest,
        items=items,
        manifest_entries=entries,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def test_previous_release_reconstruction_preserves_published_validator_snapshot(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    previous = previous_courseware_release(builtin_courseware_source)
    validate = package_node(previous.workflow_catalog, "intro.validate")
    refs = [
        *validate["validator_refs"],
        *validate["quality_report_persistence"]["validator_refs"],
        *previous.workflow_catalog["validator_descriptors"],
    ]
    restored = [ref for ref in refs if ref.get("key") == PREVIOUS_INTRO_SINGLE_ANCHOR["key"]]

    assert restored == [
        PREVIOUS_INTRO_SINGLE_ANCHOR,
        PREVIOUS_INTRO_SINGLE_ANCHOR,
        {**PREVIOUS_INTRO_SINGLE_ANCHOR, "implementation_status": "contract_only"},
    ]
    assert previous.workflow_checksum == PREVIOUS_WORKFLOW_CHECKSUM


def test_release_1_2_registry_preserves_legacy_artifact_quality_sources(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    release_1_2 = release_1_2_courseware_release(builtin_courseware_source)

    registered = BUILTIN_WORKFLOW_REGISTRY.load(release_1_2.workflow_catalog)

    assert all(
        output.quality_source_binding == "artifact"
        for output in registered.output_definition_index.values()
        if output.producer_node_key
        in {"lesson.division.generate", "lesson_plan.generate", "intro.generate_options"}
    )


def test_legacy_courseware_release_uses_v1_shape_and_fails_projection_closed(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    legacy = legacy_courseware_release(builtin_courseware_source)

    assert legacy.package_checksum == LEGACY_PACKAGE_CHECKSUM
    assert legacy.workflow_checksum == LEGACY_WORKFLOW_CHECKSUM
    assert legacy.workflow_catalog["api_version"] == LEGACY_WORKFLOW_CATALOG_API_VERSION
    assert "external_input_contract_refs" not in legacy.workflow_catalog
    assert "validator_descriptors" not in legacy.workflow_catalog
    assert all(
        "output_persistence" not in node
        and "execution_scope" not in node
        and "dependencies" not in node
        for node in legacy.workflow_catalog["nodes"]
    )
    registered = BUILTIN_WORKFLOW_REGISTRY.load(legacy.workflow_catalog)
    assert registered.supports_output_projection is False
    with pytest.raises(WorkflowDefinitionError) as caught:
        registered.require_output_projection()
    assert caught.value.code == "WORKFLOW_RELEASE_UNSUPPORTED"


def snapshot_publication_rows(
    session: Session,
    result: PublicationResult,
) -> tuple[object, ...]:
    def values(row: object | None) -> tuple[tuple[str, object], ...]:
        assert row is not None
        return tuple(
            (attribute.key, deepcopy(getattr(row, attribute.key)))
            for attribute in inspect(row).mapper.column_attrs
        )

    package_version = session.get(ContentPackageVersion, result.content_package_version_id)
    assert package_version is not None
    rows = (
        session.get(ContentPackage, package_version.content_package_id),
        package_version,
        session.get(ContentRelease, result.content_release_id),
        session.get(WorkflowDefinitionVersion, result.workflow_definition_version_id),
        session.scalar(
            select(ContentReleaseItem).where(
                ContentReleaseItem.content_release_id == result.content_release_id
            )
        ),
        session.scalar(
            select(RuntimeDefaultVersion).where(
                RuntimeDefaultVersion.content_release_id == result.content_release_id,
                RuntimeDefaultVersion.workflow_definition_version_id
                == result.workflow_definition_version_id,
            )
        ),
    )
    return (
        *(values(row) for row in rows),
        tuple(
            sorted(
                values(row)
                for row in session.scalars(
                    select(ContentPackageItemVersion).where(
                        ContentPackageItemVersion.content_package_version_id == package_version.id
                    )
                )
            )
        ),
        tuple(
            sorted(
                values(row)
                for row in session.scalars(
                    select(ContentDefinitionVersion).where(
                        ContentDefinitionVersion.content_package_version_id == package_version.id
                    )
                )
            )
        ),
    )


def test_golden_release_is_published_from_validated_fixtures_and_is_idempotent(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        first = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        counts_after_first = publication_counts(session)
        second = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )

        package_version = session.get(ContentPackageVersion, first.content_package_version_id)
        release = session.get(ContentRelease, first.content_release_id)
        workflow = session.get(
            WorkflowDefinitionVersion,
            first.workflow_definition_version_id,
        )
        release_item = session.scalar(
            select(ContentReleaseItem).where(
                ContentReleaseItem.content_release_id == first.content_release_id
            )
        )

        assert first.created is True
        assert second.created is False
        assert second == first.as_existing()
        assert publication_counts(session) == counts_after_first
        assert source.semantic_version == "1.4.0"
        assert source.manifest["semantic_version"] == "1.4.0"
        assert source.workflow_catalog["semantic_version"] == "1.4.0"
        assert source.release_key == f"{source.package_key}@1.4.0"
        assert package_version is not None
        assert package_version.semantic_version == "1.4.0"
        assert package_version.manifest_json == source.manifest
        assert package_version.manifest_json["semantic_version"] == "1.4.0"
        assert package_version.checksum == source.package_checksum
        assert release is not None and release.status == "published"
        assert release.release_key == source.release_key
        assert release_item is not None
        assert release_item.content_package_version_id == package_version.id
        assert workflow is not None
        assert workflow.graph_json == source.workflow_catalog
        assert workflow.checksum == source.workflow_checksum
        assert session.scalar(
            select(func.count())
            .select_from(ContentPackageItemVersion)
            .where(ContentPackageItemVersion.content_package_version_id == package_version.id)
        ) == len(source.items)
        assert (
            session.scalar(
                select(func.count())
                .select_from(ContentDefinitionVersion)
                .where(ContentDefinitionVersion.content_package_version_id == package_version.id)
            )
            == source.content_definition_count
        )
        definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.content_package_version_id == package_version.id,
                ContentDefinitionVersion.definition_key == "lesson.division.generate.output",
            )
        )
        assert definition is not None
        validator = Draft202012Validator(definition.schema_json)
        assert list(validator.iter_errors({}))
        assert list(validator.iter_errors({"unexpected": True}))
        assert definition.schema_json["properties"]["lesson_count"]["minimum"] == 1
        minimum_report = ArtifactValidation.validation_report(
            definition,
            {"lesson_count": 0, "lesson_units": []},
        )
        assert any(error["path"] == ["lesson_count"] for error in minimum_report["errors"])
        count_report = ArtifactValidation.validation_report(
            definition,
            {"lesson_count": 2, "lesson_units": [{}]},
        )
        assert any(
            error["path"] == ["lesson_count"] and "number of items" in error["message"]
            for error in count_report["errors"]
        )
        assert resolve_runtime_defaults(session).content_release_id == release.id
        assert resolve_runtime_defaults(session).workflow_definition_version_id == workflow.id


def test_forward_publication_preserves_legacy_release_and_project_bindings(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)
    legacy = legacy_courseware_release(source)

    assert legacy.package_key == source.package_key
    assert (
        legacy.manifest["semantic_version"]
        == legacy.semantic_version
        == legacy.workflow_catalog["semantic_version"]
        == "1.0.0"
    )
    assert legacy.package_checksum == canonical_json_sha256(legacy.manifest)
    assert legacy.package_checksum == LEGACY_PACKAGE_CHECKSUM
    assert (
        legacy.workflow_checksum
        == hashlib.sha256(canonical_catalog_json(legacy.workflow_catalog)).hexdigest()
    )
    assert legacy.workflow_checksum == LEGACY_WORKFLOW_CHECKSUM
    assert legacy.package_checksum != source.package_checksum
    assert legacy.workflow_checksum != source.workflow_checksum

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        request = CreateProjectRequest(title="Legacy release", knowledge_point="One half")
        old_result = ContentReleasePublisher(session).publish(
            legacy,
            published_by=actor.principal_id,
        )
        old_project = ProjectRepository(session, actor).create(request)

        old_package_version = session.get(
            ContentPackageVersion,
            old_result.content_package_version_id,
        )
        old_release = session.get(ContentRelease, old_result.content_release_id)
        old_workflow = session.get(
            WorkflowDefinitionVersion,
            old_result.workflow_definition_version_id,
        )
        assert old_package_version is not None
        assert old_release is not None
        assert old_workflow is not None
        old_package = session.get(ContentPackage, old_package_version.content_package_id)
        assert old_package is not None
        assert old_result.created is True
        assert old_package_version.semantic_version == legacy.semantic_version == "1.0.0"
        assert old_package_version.manifest_json == legacy.manifest
        assert old_package_version.checksum == legacy.package_checksum
        assert old_release.release_key == legacy.release_key
        assert old_release.release_key == f"{source.package_key}@1.0.0"
        assert old_workflow.graph_json == legacy.workflow_catalog
        assert old_workflow.checksum == legacy.workflow_checksum

        old_snapshot = snapshot_publication_rows(session, old_result)
        old_project_binding = (
            old_project.content_release_id,
            old_project.workflow_definition_version_id,
        )
        counts_after_legacy = publication_counts(session)

        current_result = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        new_project = ProjectRepository(session, actor).create(
            request.model_copy(update={"title": "Current release"})
        )

        current_package_version = session.get(
            ContentPackageVersion,
            current_result.content_package_version_id,
        )
        current_release = session.get(ContentRelease, current_result.content_release_id)
        current_workflow = session.get(
            WorkflowDefinitionVersion,
            current_result.workflow_definition_version_id,
        )
        assert current_package_version is not None
        assert current_release is not None
        assert current_workflow is not None
        assert current_result.created is True
        assert current_result.content_package_version_id != old_package_version.id
        assert current_result.content_release_id != old_release.id
        assert current_result.workflow_definition_version_id != old_workflow.id
        assert current_package_version.content_package_id == old_package.id
        assert current_package_version.semantic_version == source.semantic_version == "1.4.0"
        assert current_package_version.manifest_json == source.manifest
        assert current_package_version.checksum == source.package_checksum
        assert current_release.release_key == source.release_key
        assert current_release.release_key == f"{source.package_key}@1.4.0"
        assert current_workflow.graph_json == source.workflow_catalog
        assert current_workflow.checksum == source.workflow_checksum
        assert old_result.content_release_id == old_project.content_release_id
        assert (
            old_result.workflow_definition_version_id == old_project.workflow_definition_version_id
        )
        assert new_project.content_release_id == current_result.content_release_id
        assert (
            new_project.workflow_definition_version_id
            == current_result.workflow_definition_version_id
        )
        assert old_project_binding == (
            old_project.content_release_id,
            old_project.workflow_definition_version_id,
        )

        counts_after_current = publication_counts(session)
        assert counts_after_current != counts_after_legacy
        replay = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        assert replay.created is False
        assert replay == current_result.as_existing()
        assert publication_counts(session) == counts_after_current

        session.expire_all()
        session.refresh(old_project)
        assert (
            old_project.content_release_id,
            old_project.workflow_definition_version_id,
        ) == old_project_binding

        assert snapshot_publication_rows(session, old_result) == old_snapshot


def test_release_1_2_preserves_1_1_rows_and_existing_project_binding(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    current_source = load_builtin_courseware_release(ROOT)
    source = release_1_2_courseware_release(current_source)
    previous = previous_courseware_release(current_source)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        previous_result = ContentReleasePublisher(session).publish(
            previous,
            published_by=actor.principal_id,
        )
        existing = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Bound to 1.1.0", knowledge_point="One half")
        )
        previous_snapshot = snapshot_publication_rows(session, previous_result)
        previous_binding = (
            existing.content_release_id,
            existing.workflow_definition_version_id,
        )

        current_result = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        current = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Bound to 1.4.0", knowledge_point="One half")
        )

        assert previous.semantic_version == "1.1.0"
        assert previous.package_checksum == PREVIOUS_PACKAGE_CHECKSUM
        assert previous.workflow_checksum == PREVIOUS_WORKFLOW_CHECKSUM
        assert source.semantic_version == "1.4.0"
        assert previous_result.content_release_id != current_result.content_release_id
        assert (
            current.content_release_id,
            current.workflow_definition_version_id,
        ) == (
            current_result.content_release_id,
            current_result.workflow_definition_version_id,
        )
        session.expire_all()
        session.refresh(existing)
        assert (
            existing.content_release_id,
            existing.workflow_definition_version_id,
        ) == previous_binding
        assert snapshot_publication_rows(session, previous_result) == previous_snapshot


def test_release_1_4_preserves_1_2_rows_and_existing_project_binding(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)
    previous = release_1_2_courseware_release(source)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        previous_result = ContentReleasePublisher(session).publish(
            previous,
            published_by=actor.principal_id,
        )
        existing = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Bound to 1.2.0", knowledge_point="One half")
        )
        previous_snapshot = snapshot_publication_rows(session, previous_result)
        previous_binding = (
            existing.content_release_id,
            existing.workflow_definition_version_id,
        )

        current_result = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        current = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Bound to 1.4.0", knowledge_point="One half")
        )

        assert previous.semantic_version == "1.2.0"
        assert previous.package_checksum == RELEASE_1_2_PACKAGE_CHECKSUM
        assert previous.workflow_checksum == RELEASE_1_2_WORKFLOW_CHECKSUM
        assert source.semantic_version == "1.4.0"
        assert previous_result.content_release_id != current_result.content_release_id
        assert (
            current.content_release_id,
            current.workflow_definition_version_id,
        ) == (
            current_result.content_release_id,
            current_result.workflow_definition_version_id,
        )
        session.expire_all()
        session.refresh(existing)
        assert (
            existing.content_release_id,
            existing.workflow_definition_version_id,
        ) == previous_binding
        assert snapshot_publication_rows(session, previous_result) == previous_snapshot


def test_publishing_new_default_only_changes_projects_created_after_activation(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        request = CreateProjectRequest(title="Before publish", knowledge_point="One half")
        existing = ProjectRepository(session, actor).create(request)
        published = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        newer = ProjectRepository(session, actor).create(
            request.model_copy(update={"title": "After publish"})
        )

        session.refresh(existing)
        assert existing.content_release_id == BUILTIN_RUNTIME_DEFAULTS.content_release_id
        assert (
            existing.workflow_definition_version_id
            == BUILTIN_RUNTIME_DEFAULTS.workflow_definition_version_id
        )
        assert newer.content_release_id == published.content_release_id
        assert newer.workflow_definition_version_id == published.workflow_definition_version_id


def test_failed_publication_rolls_back_every_new_runtime_row(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)

    with factory() as session, session.begin():
        with pytest.raises(IntegrityError):
            ContentReleasePublisher(session).publish(source, published_by=uuid4())

        assert (
            session.scalar(
                select(func.count())
                .select_from(ContentPackage)
                .where(ContentPackage.package_key == source.package_key)
            )
            == 0
        )
        assert resolve_runtime_defaults(session) == BUILTIN_RUNTIME_DEFAULTS


def test_published_package_item_cannot_be_moved_to_a_draft_package(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        published = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        published_version = session.get(
            ContentPackageVersion,
            published.content_package_version_id,
        )
        assert published_version is not None
        draft = ContentPackageVersion(
            id=new_uuid7(),
            content_package_id=published_version.content_package_id,
            semantic_version="0.0.0-trigger-test",
            runtime_constraint=source.runtime_constraint,
            manifest_json={},
            archive_asset_version_id=None,
            checksum="0" * 63 + "1",
            status="draft",
            validated_at=utc_now(),
            published_at=None,
        )
        session.add(draft)
        session.flush()
        item = session.scalar(
            select(ContentPackageItemVersion).where(
                ContentPackageItemVersion.content_package_version_id == published_version.id
            )
        )
        assert item is not None
        with pytest.raises(IntegrityError), session.begin_nested():
            item.content_package_version_id = draft.id
            session.flush()


def test_concurrent_first_publication_is_serialized_and_replayed(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)
    lock_acquired = Event()
    allow_first_to_continue = Event()

    class BlockingPublisher(ContentReleasePublisher):
        def _lock_publication(self) -> None:
            super()._lock_publication()
            lock_acquired.set()
            if not allow_first_to_continue.wait(timeout=10):
                raise TimeoutError("test did not release the first publication")

    def publish(*, blocking: bool):
        with factory() as session, session.begin():
            publisher_type = BlockingPublisher if blocking else ContentReleasePublisher
            return publisher_type(session).publish(
                source,
                published_by=SYSTEM_PRINCIPAL_ID,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(publish, blocking=True)
        assert lock_acquired.wait(timeout=5)
        second_future = executor.submit(publish, blocking=False)
        try:
            time.sleep(0.2)
            assert not second_future.done()
        finally:
            allow_first_to_continue.set()
        first = first_future.result(timeout=10)
        second = second_future.result(timeout=10)

    assert first.created is True
    assert second == first.as_existing()


def test_published_content_blocks_destructive_migration_downgrade(
    migrated_database_url: str,
) -> None:
    first = run_publish_cli(migrated_database_url)
    assert first.returncode == 0, first.stderr
    previous = os.environ.get("SHANHAI_DATABASE_URL")
    os.environ["SHANHAI_DATABASE_URL"] = migrated_database_url
    try:
        with pytest.raises(DBAPIError, match="cannot downgrade published content"):
            command.downgrade(Config("alembic.ini"), "f1a6c3e9b205")
    finally:
        if previous is None:
            os.environ.pop("SHANHAI_DATABASE_URL", None)
        else:
            os.environ["SHANHAI_DATABASE_URL"] = previous

    replay = run_publish_cli(migrated_database_url)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)["created"] is False


def test_administrative_cli_publishes_and_replays_without_new_versions(
    migrated_database_url: str,
) -> None:
    first_process = run_publish_cli(migrated_database_url)
    assert first_process.returncode == 0, first_process.stderr
    first = json.loads(first_process.stdout)
    assert first["conclusion"] == "passed"
    assert first["created"] is True
    assert first["runtime_default_version_no"] == 2

    second_process = run_publish_cli(migrated_database_url)
    assert second_process.returncode == 0, second_process.stderr
    second = json.loads(second_process.stdout)
    assert second["created"] is False
    assert second["content_release_id"] == first["content_release_id"]


def run_publish_cli(database_url: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["SHANHAI_DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "apps.api.cli", "publish-golden-content"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def publication_counts(session) -> tuple[int, ...]:
    models = (
        ContentPackage,
        ContentPackageVersion,
        ContentPackageItemVersion,
        ContentDefinitionVersion,
        ContentRelease,
        ContentReleaseItem,
        WorkflowDefinitionVersion,
        RuntimeDefaultVersion,
    )
    return tuple(session.scalar(select(func.count()).select_from(model)) or 0 for model in models)
