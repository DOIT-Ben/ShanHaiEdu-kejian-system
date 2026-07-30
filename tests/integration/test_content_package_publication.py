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
RELEASE_1_3_PACKAGE_CHECKSUM = "5a0c06b7e3d7e3b40d367ed7928bd6ced6477742a044e9bb2e192d313cd4056c"
RELEASE_1_3_WORKFLOW_CHECKSUM = "f3cd43a907eaf5d3b11c3d16352cbeae542a46a7ea2c9706c96f74cfbc576cc6"
RELEASE_1_3_CHANGE_SUMMARY = (
    "前向发布PPT页面装配与PPTX导出的确定性输出定义，并保持旧Release与既有项目绑定不变。"  # noqa: RUF001
)
RELEASE_1_4_PACKAGE_CHECKSUM = "af33618377f6f83801582889e7bfc607849320119fc1a2ae932513686cbfcd47"
RELEASE_1_4_WORKFLOW_CHECKSUM = "ffbc093cd188b45aee2d8c49481f2ddec71a77da6e40fe4e7b5ef63d10a36d0f"
RELEASE_1_4_CHANGE_SUMMARY = (
    "在不可变1.3.0基础上前向补齐教材范围ContentDefinition与human-gate Artifact批准合同；"  # noqa: RUF001
    "旧Release与既有项目绑定保持不变。"
)
RELEASE_1_5_PACKAGE_CHECKSUM = "7e9535f36d30ef1dda4f2e630e36754d0a9ae04493b505db90f78fccc02c1a76"
RELEASE_1_5_WORKFLOW_CHECKSUM = "fcc935a66e7a384dd04c9348e5b0858bed5b2ba650d20dec307c3a32681b77c5"
RELEASE_1_5_CHANGE_SUMMARY = (
    "在不可变1.4.0基础上前向修正三类九套真实教材证据兼容与方案唯一性校验；"  # noqa: RUF001
    "旧Release与既有项目绑定保持不变。"
)
RELEASE_1_5_LESSON_DIVISION_PROMPT_SHA256 = (
    "53271e4e0b409236444ffafc3e93200d9fcbb7bf1f1947e338e42f106abbf93e"
)
RELEASE_1_5_LESSON_DIVISION_OUTPUT_SHA256 = (
    "5b5cc8bd1efee1a3b1a817a55f4a8a57ba7a720dced84d2d4561f97c914f979c"
)
RELEASE_1_5_LESSON_DIVISION_METHOD = (
    "先分析批准范围中的知识结构、前后联系、例题或活动层次和学生可能的认知转折，再划分课时。"  # noqa: RUF001
    "默认按40分钟容量，由直观经验到抽象表示、由概念形成到应用练习；新授课每课时聚焦一个核心知识或方法，"  # noqa: RUF001
    "不把多个难点强塞在一起。若同页包含多个认知层次，按认知难度而非机械页码拆分；若材料只包含一个容量适当的"  # noqa: RUF001
    "小知识点，保留单课时，不为凑结构增加练习课或复习课。每课时写明稳定键、顺序、课型、核心学习结果、教材范围"  # noqa: RUF001
    "与证据、前置基础、讲授边界、不得提前讲授、重点、难点、划分理由和后续衔接。指定课时数与容量或知识边界冲突时，"  # noqa: RUF001
    "在待确认问题中如实报告，不牺牲理解过程硬塞。"  # noqa: RUF001
)
RELEASE_1_5_LESSON_PLAN_PROMPT_SHA256 = (
    "749b1baad411fb74272e0e253147f551186523494c8e5ce59ac5029cf3d05e8b"
)
RELEASE_1_5_LESSON_PLAN_OUTPUT_SHA256 = (
    "5ecbbef08390810ddedf0ae84e30592ab49978dec213900d254bcb0604f1a733"
)
RELEASE_1_5_INTRO_OUTPUT_SHA256 = "b9cc12772863821d328889319cd958108f49f4d5af296839869bce237099cd0a"
RELEASE_1_5_1_PACKAGE_CHECKSUM = "724d95b532b1f181f0ea428cab5d83cb5e142e41b00a3cbaa3bbdb49139d90f8"
RELEASE_1_5_1_WORKFLOW_CHECKSUM = "017995664712052bd8652c4ac2094f3881ad1ad8e087675bf975c2875513b79c"
RELEASE_1_5_2_PACKAGE_CHECKSUM = "b63286ddb941d98b9f5ac0699b17ae2b51eae03f641838a98daa755454911629"
RELEASE_1_5_2_WORKFLOW_CHECKSUM = "a2e5dafe66c0138bc2f997e74bdf5d14944f1b5d65a9929f914aae592220ba3d"
RELEASE_1_5_3_PACKAGE_CHECKSUM = "dc0f8525e0a8689ee6bdb6a98d9e20c997203e5c9e0bbe8c51431665f433b1de"
RELEASE_1_5_3_WORKFLOW_CHECKSUM = "df1c93a078df788d262be773997e5e7d2812b7c2c2d55d2244b820ab47f5b9f4"
RELEASE_1_5_3_CHANGE_SUMMARY = (
    "在不可变1.5.2基础上前向修正三类九套质量校验对教师适配说明中讲授边界复述的误判；"  # noqa: RUF001
    "旧Release与既有项目绑定保持不变。"
)
RELEASE_1_5_3_VIDEO_ITEM_HASHES = {
    "video.shots.generate.input": (
        "f4287a720162efbf1446b5c71d42760366463a1f995f0451697bf2bd041ee749"
    ),
    "video.shots.generate.output": (
        "b895b7da15db97e1921b4e2dbed2377c864c369a49762fd90cb94cd76efbfc93"
    ),
    "video.shots.generate.prompt": (
        "1c02507795764b560182086a94867ddd6e383947da58b0a48966633337fe8ecc"
    ),
    "video.shots.generate.projection": (
        "be4de484c95db3b8c506d2c361ede3aa68b38faa3dc6e282d878eb34d5517bfb"
    ),
    "video.shots.generate": "a313a2f7eebd3daad7238fa68944dcac1dfe5001d74ff5eb18bbcb41407ab4aa",
}
RELEASE_1_5_2_CHANGE_SUMMARY = (
    "在不可变1.5.1基础上把三类九套改为候选生成与独立统一评分两个受审计阶段，删除辅助倾向字段与跨倾向门禁；"  # noqa: RUF001
    "旧Release与既有项目绑定保持不变。"
)
RELEASE_1_5_1_CHANGE_SUMMARY = (
    "在不可变1.5.0基础上前向强化十二部分教案的教材范围与评价证据引用约束，并收紧三类九套的方案键、"  # noqa: RUF001
    "媒介与数值输出约束；旧Release与既有项目绑定保持不变。"  # noqa: RUF001
)
RELEASE_1_5_1_INTRO_PROMPT_SHA256 = (
    "4a38faaeec92bcd61151eb172a3517e4b00024b04986260cf0ad7342b4e3486d"
)
RELEASE_1_5_1_INTRO_OUTPUT_SHA256 = (
    "16ef79ffae29ed44a6c82b2b1b0a7a6b2489be2b205459e27694671bfcbfe674"
)
RELEASE_1_5_1_INTRO_GENERATION_SHA256 = (
    "b898282ebe7917d0b454694906d62feea1bf580e37073a9c6c61cba8ba9dad06"
)
RELEASE_1_5_1_EVALUATION_ITEM_KEYS = frozenset(
    {
        "intro.generate_options.candidates.output",
        "intro.generate_options.evaluation.output",
        "intro.generate_options.evaluation.prompt",
    }
)
RELEASE_1_5_LESSON_PLAN_METHOD = (
    "先确定本课前置基础、核心学习结果、后续衔接和不得提前讲授内容；再写可观察、可评价且有成功标准的目标，"  # noqa: RUF001
    "并让每个目标同时绑定教学环节和评价证据。按设定课时长度设计学习启动、核心探究、应用或评价、课堂收束，"  # noqa: RUF001
    "全部环节时间之和必须等于课时长度。每个环节写清教师活动、学生活动、关键问题、预设回答、可能错误、追问支架、"
    "评价证据、板书增量、过渡和设计意图。学情区分已确认事实、审慎的一般性判断和未知项；分层作业符合年级并提供标准。"  # noqa: RUF001
    "教学反思只提供课后问题和空白记录，不能伪造授课结果。"  # noqa: RUF001
)
RELEASE_1_5_LESSON_PLAN_QUALITY_GATE = (
    "输出顶层字段必须且只能按当前内容定义包含教学内容、教材分析、学情分析、设计意图、教学目标、教学重难点及突破策略、"
    "教学准备、教学过程、板书设计、课堂总结、分层作业和教学反思十二部分。不得使用不可评价的空泛目标，不得虚构班级掌握率"  # noqa: RUF001
    "或设备，不得超出批准教材，不得把准确答案提前放入导入。正文删除任何导入附录后仍须完整可试讲；结构、目标引用、"  # noqa: RUF001
    "证据引用和时间总量必须通过校验。"
)
RELEASE_1_4_INTRO_OPTION_SCHEMA = {
    "key": "validator.intro.option_set_schema",
    "semantic_version": "1.0.0",
    "implementation_digest": "2049fe72e70c9c5280e011cfd131b47d7444128973c4e7163c2c51d08d18a379",
}
RELEASE_1_5_1_INTRO_OPTION_SCHEMA = {
    "key": "validator.intro.option_set_schema",
    "semantic_version": "1.1.0",
    "implementation_digest": "d60f89477c8db4c3f116fa7e524b8b8688e4f5403cc8cb137b0f1d56a170e6e4",
}
RELEASE_1_4_INTRO_SINGLE_ANCHOR = {
    "key": "validator.intro.single_anchor",
    "semantic_version": "1.1.0",
    "implementation_digest": "f37001db813669d7148ac43d25045472c0c4b84427df414e303f4a99e5b40220",
}
RELEASE_1_5_2_INTRO_SINGLE_ANCHOR = {
    "key": "validator.intro.single_anchor",
    "semantic_version": "1.2.0",
    "implementation_digest": "c63f73f6b74e54bf0a69ca7770f13a76e56bb6f092cf523d2eb2d612eae5ca06",
}
RELEASE_1_4_LESSON_PLAN_SCOPE = {
    "key": "validator.lesson_plan.scope",
    "semantic_version": "1.0.0",
    "implementation_digest": "72de7b0aa6677502ef36f29339badaf432b37c0b0409e22236efd5b03f99b68b",
}
RELEASE_1_4_LESSON_PLAN_TEACHING_QUALITY = {
    "key": "validator.lesson_plan.teaching_quality",
    "semantic_version": "1.0.0",
    "implementation_digest": "10296a5dfb1da0fdd73f8be5bf04fd597b37f934ef492dbe58edd7ac58afbdf2",
}
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


def restore_release_1_4_validators(catalog: dict[str, Any]) -> None:
    intro_generate = package_node(catalog, "intro.generate_options")
    intro_validate = package_node(catalog, "intro.validate")
    replace_validator_ref(intro_generate["validator_refs"], RELEASE_1_4_INTRO_OPTION_SCHEMA)
    for refs in (
        intro_validate["validator_refs"],
        intro_validate["quality_report_persistence"]["validator_refs"],
        catalog["validator_descriptors"],
    ):
        replace_validator_ref(refs, RELEASE_1_4_INTRO_OPTION_SCHEMA)
        replace_validator_ref(refs, RELEASE_1_4_INTRO_SINGLE_ANCHOR)
    lesson_plan_generate = package_node(catalog, "lesson_plan.generate")
    lesson_plan_validate = package_node(catalog, "lesson_plan.validate")
    for refs in (
        lesson_plan_generate["validator_refs"],
        lesson_plan_validate["validator_refs"],
        lesson_plan_validate["quality_report_persistence"]["validator_refs"],
        catalog["validator_descriptors"],
    ):
        replace_validator_ref(refs, RELEASE_1_4_LESSON_PLAN_SCOPE)
        replace_validator_ref(refs, RELEASE_1_4_LESSON_PLAN_TEACHING_QUALITY)


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


def restore_lesson_plan_output_before_1_5_1(items: dict[str, dict[str, Any]]) -> None:
    output = items["lesson_plan.generate.output"]
    process = next(
        field for field in output["spec"]["fields"] if field["field_key"] == "teaching_process"
    )
    process_assessment = next(
        field
        for field in process["children"]
        if field["field_key"] == "process_assessment_evidence"
    )
    process_assessment.pop("description", None)


def restore_lesson_division_before_1_5_1(items: dict[str, dict[str, Any]]) -> None:
    prompt = items["lesson.division.generate.prompt"]
    method = next(
        section for section in prompt["spec"]["sections"] if section["section_key"] == "method"
    )
    method["content"] = RELEASE_1_5_LESSON_DIVISION_METHOD

    output = items["lesson.division.generate.output"]
    coverage = next(
        field for field in output["spec"]["fields"] if field["field_key"] == "coverage_check"
    )
    unresolved = next(
        field for field in coverage["children"] if field["field_key"] == "unresolved_questions"
    )
    unresolved["editable"] = False


def restore_intro_output_before_1_5_1(items: dict[str, dict[str, Any]]) -> None:
    output = items["intro.generate_options.output"]
    options = next(field for field in output["spec"]["fields"] if field["field_key"] == "options")
    children = {field["field_key"]: field for field in options["children"]}
    children["option_key"].pop("validation_rules", None)
    children["suggested_medium"].pop("options", None)
    children["duration_seconds"].pop("validation_rules", None)
    children["recommendation_score"].pop("validation_rules", None)


def restore_intro_before_1_5_2(items: dict[str, dict[str, Any]]) -> None:
    generation = items["intro.generate_options"]
    generation_spec = generation["spec"]
    generation_spec["description"] = (
        "以已批准课时、知识边界、最小教材证据和教师偏好，在一次生成中产出一套或三类九套最终课堂导入方案；"  # noqa: RUF001
        "完善已有创意时绑定一个exact来源版本。"
    )
    generation_spec.pop("evaluation_stage", None)

    prompt = items["intro.generate_options.prompt"]
    prompt_spec = prompt["spec"]
    prompt_spec["description"] = generation_spec["description"]
    prompt_spec["output_definition_ref"] = {
        "item_key": "intro.generate_options.output",
        "kind": "content_definition",
    }
    prompt_sections = {
        "role": "你是小学数学课程驱动的课堂导入方案设计师，擅长从知识点、学习目标、教材证据和不得提前讲授边界中设计科普、应用、故事倾向可交叉的创意方案。",  # noqa: E501, RUF001
        "task": "读取目标课时稳定键、知识点、一句话学习目标、教学内容边界、must_not_preteach、年级或年龄段、教材证据摘要及可选教师创意、媒介和时长偏好，在一次调用中直接生成最终intro_option_set。default_nine禁止已有创意来源并生成九套；refine_existing必须基于一个exact已有方案版本只完善一套。不要生成教案正文、PPT、分镜、旁白、字幕、资产、Provider参数或费用。",  # noqa: E501, RUF001
        "method": "先提取课程种子，再从可观察现象、真实任务、人物或主体目标等不同角度生成创意；课程依据必须从创意形成开始参与，不能在完成后补贴课题词。每套同时形成主要与辅助倾向、创意概念、钩子、观看价值、课程关联、课堂第一问、交接时刻、不得提前讲授、媒介、时长、适配、风险和推荐结论。science、application、story只是主要倾向，辅助倾向可以交叉。",  # noqa: E501, RUF001
        "quality_gate": "default_nine来源版本为0、主要倾向各恰好三套且至少一套包含两个以上辅助倾向；refine_existing来源版本恰好1且方案恰好1套。每套必须可追溯目标课时、知识点和教材证据，创意与课程依据存在实质关联；不得提前讲出需要学生发现的定义、写法、方法或结论；default_nine最高推荐分必须唯一；不得把三种倾向解释为互斥类别；输出不含完整教案、PPT、视频产物、Provider和费用。",  # noqa: E501, RUF001
    }
    for section in prompt_spec["sections"]:
        section["content"] = prompt_sections[section["section_key"]]

    output = items["intro.generate_options.output"]
    output_spec = output["spec"]
    output_spec["description"] = (
        "一套或三类九套完整导入方案、0或1个exact来源版本、默认路径唯一最高推荐分和可冻结选择快照。"
    )
    options = next(field for field in output_spec["fields"] if field["field_key"] == "options")
    primary_index = next(
        index
        for index, field in enumerate(options["children"])
        if field["field_key"] == "primary_tendency"
    )
    options["children"].insert(
        primary_index + 1,
        {
            "field_key": "secondary_tendencies",
            "label": "辅助创作倾向",
            "type": "list",
            "required": True,
            "editable": True,
            "deletable": False,
        },
    )


def restore_release_1_5_1_validator(catalog: dict[str, Any]) -> None:
    intro_generate = package_node(catalog, "intro.generate_options")
    intro_validate = package_node(catalog, "intro.validate")
    for refs in (
        intro_generate["validator_refs"],
        intro_validate["validator_refs"],
        intro_validate["quality_report_persistence"]["validator_refs"],
        catalog["validator_descriptors"],
    ):
        replace_validator_ref(refs, RELEASE_1_5_1_INTRO_OPTION_SCHEMA)


def restore_release_1_5_2_validator(catalog: dict[str, Any]) -> None:
    intro_validate = package_node(catalog, "intro.validate")
    for refs in (
        intro_validate["validator_refs"],
        intro_validate["quality_report_persistence"]["validator_refs"],
        catalog["validator_descriptors"],
    ):
        replace_validator_ref(refs, RELEASE_1_5_2_INTRO_SINGLE_ANCHOR)


def restore_video_before_1_6(items: dict[str, dict[str, Any]]) -> None:
    title = "逐镜头候选视频生成"
    description = "按细分镜逐shot生成候选视频，候选通过校验、采用并保存后才形成正式clip。"  # noqa: RUF001
    for item_key in (
        "video.shots.generate",
        "video.shots.generate.input",
        "video.shots.generate.output",
        "video.shots.generate.prompt",
        "video.shots.generate.projection",
    ):
        item = items[item_key]
        suffix = item_key.removeprefix("video.shots.generate").removeprefix(".")
        label = {
            "": title,
            "input": f"{title}输入",
            "output": f"{title}输出",
            "prompt": f"{title}业务Prompt",
            "projection": f"{title}教师投影",
        }[suffix]
        item["metadata"]["name"] = label
        item["spec"]["title"] = label
    items["video.shots.generate"]["spec"]["description"] = description

    input_spec = items["video.shots.generate.input"]["spec"]
    input_spec["description"] = "输入一个shot合同、视频风格、候选数及必需关键帧与连续性参考。"
    input_spec["fields"] = [
        {
            "field_key": "shot_spec_ref",
            "label": "细分镜shot",
            "value_type": "reference",
            "required": True,
            "source": "system",
            "visibility": "hidden",
            "widget": "textarea",
        },
        {
            "field_key": "shot_candidate_count",
            "label": "候选数量",
            "value_type": "number",
            "required": True,
            "source": "teacher",
            "visibility": "primary",
            "widget": "number",
            "default_value": 2,
            "validation": {"minimum": 1, "maximum": 4},
        },
        {
            "field_key": "shot_generation_quality",
            "label": "逻辑质量档位",
            "value_type": "enum",
            "required": True,
            "source": "teacher",
            "visibility": "secondary",
            "widget": "select",
            "default_value": "balanced",
            "options": [
                {"value": "fast", "label": "快速"},
                {"value": "balanced", "label": "均衡"},
                {"value": "quality", "label": "高质量"},
            ],
        },
        {
            "field_key": "shot_reference_assets",
            "label": "关键帧与连续性参考",
            "value_type": "asset",
            "required": True,
            "source": "system",
            "visibility": "hidden",
            "widget": "asset_picker",
        },
        {
            "field_key": "shot_style_contract_ref",
            "label": "视频风格合同",
            "value_type": "reference",
            "required": True,
            "source": "system",
            "visibility": "hidden",
            "widget": "textarea",
        },
    ]

    prompt_spec = items["video.shots.generate.prompt"]["spec"]
    prompt_spec["description"] = description
    old_sections = {
        "role": "你是服务端逐shot视频生成执行器。",
        "task": "严格按一个已冻结shot合同生成指定数量候选，按image_index顺序传入shot_keyframe和continuity_reference，不改写故事、时长、动作或固定槽位。",  # noqa: E501, RUF001
        "method": "通过模型网关选择满足video.image_to_video.6s_30s能力的路由；只传节点允许的参考资产与业务提示词。记录候选键、实际时长、分辨率、帧率、媒体类型、SHA-256和质量标记。候选阶段不创建clip_id；只有校验通过、被采用并原子保存到shot槽位后才形成正式clip。",  # noqa: E501, RUF001
        "quality_gate": "输出可播放且时长匹配6至30秒shot合同；首尾状态、主体身份、资产、动作、光线和镜头连续；无文字字幕水印Logo和儿童安全问题；失败只影响当前shot；Provider私有参数和临时URL不进入业务产物。",  # noqa: E501, RUF001
    }
    for section in prompt_spec["sections"]:
        section["content"] = old_sections[section["section_key"]]
    prompt_spec["context_bindings"] = []


def restore_video_catalog_before_1_6(catalog: dict[str, Any]) -> None:
    master_script = package_node(catalog, "video.master_script.generate")
    master_script["dependencies"] = []
    master_script["entrypoint"] = True

    shots = package_node(catalog, "video.shots.generate")
    shots["title"] = "逐镜头候选视频生成"
    shots["input_contract_refs"] = ["artifact:video_fine_storyboard", "contract:video_style"]
    shots["context_policy"] = {"mode": "none", "allowed_sources": [], "forbidden_sources": []}
    shots["reference_asset_policy"]["roles"] = [
        {
            "role_key": "shot_keyframe",
            "requirement": "required",
            "media_types": ["image"],
            "min_items": 1,
            "max_items": 3,
            "order_mode": "stable_by_role_then_version",
            "allowed_sources": ["artifact_version", "asset_slot_current"],
            "provider_exposure": ["signed_url", "provider_file_id", "inline_bytes"],
        },
        {
            "role_key": "continuity_reference",
            "requirement": "optional",
            "media_types": ["image", "video"],
            "min_items": 0,
            "max_items": 2,
            "order_mode": "stable_by_role_then_version",
            "allowed_sources": ["artifact_version", "asset_slot_current", "creation_result"],
            "provider_exposure": ["signed_url", "provider_file_id"],
        },
    ]
    continuity_validator = next(
        descriptor
        for descriptor in catalog["validator_descriptors"]
        if descriptor["key"] == "validator.video.continuity"
    )
    shots["validator_refs"].insert(
        2,
        {
            key: continuity_validator[key]
            for key in ("key", "semantic_version", "implementation_digest")
        },
    )
    shots["dependencies"] = ["video.fine_storyboard.generate"]
    shots["entrypoint"] = False
    shots["output_persistence"]["artifact"]["relations"] = [
        {
            "source_binding": "artifact:video_fine_storyboard",
            "relation_type": "derives_from",
            "binding_key": "upstream.artifact.video_fine_storyboard",
            "impact_scope": {"mode": "all"},
        }
    ]
    package_node(catalog, "audio.plan.generate")["dependencies"] = ["video.clips.select"]
    catalog["external_input_contract_refs"].remove("asset:shot_keyframe")


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
    restore_lesson_division_before_1_5_1(items)
    restore_lesson_plan_output_before_1_5_1(items)
    restore_video_before_1_6(items)
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


def release_1_2_courseware(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    return release_1_2_courseware_release(source)


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
    release_1_5 = release_1_5_courseware_release(source)
    manifest = deepcopy(release_1_5.manifest)
    manifest["semantic_version"] = "1.2.0"
    manifest["change_summary"] = RELEASE_1_2_CHANGE_SUMMARY
    manifest["items"] = [
        entry
        for entry in manifest["items"]
        if entry["item_key"] not in {*RELEASE_1_3_ITEM_KEYS, "material.scope_review.output"}
    ]
    entries = {entry["item_key"]: entry for entry in manifest["items"]}
    items = {item_key: deepcopy(release_1_5.items[item_key]) for item_key in entries}

    catalog = deepcopy(release_1_5.workflow_catalog)
    catalog["semantic_version"] = "1.2.0"
    restore_release_1_4_validators(catalog)
    for node_key in (
        "lesson.division.generate",
        "lesson_plan.generate",
        "intro.generate_options",
    ):
        package_node(catalog, node_key)["output_persistence"].pop("quality_source_binding")
    package_node(catalog, "ppt.pages.assemble").pop("output_persistence")
    package_node(catalog, "pptx.export").pop("output_persistence")
    package_node(catalog, "material.scope_review").pop("output_persistence")

    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if (
        package_checksum != RELEASE_1_2_PACKAGE_CHECKSUM
        or workflow_checksum != RELEASE_1_2_WORKFLOW_CHECKSUM
    ):
        raise AssertionError("1.2.0 release checksum differs from the published snapshot")
    return replace(
        release_1_5,
        manifest=manifest,
        items=items,
        manifest_entries=entries,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def release_1_3_courseware_release(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    release_1_5 = release_1_5_courseware_release(source)
    manifest = deepcopy(release_1_5.manifest)
    manifest["semantic_version"] = "1.3.0"
    manifest["change_summary"] = RELEASE_1_3_CHANGE_SUMMARY
    manifest["items"] = [
        entry for entry in manifest["items"] if entry["item_key"] != "material.scope_review.output"
    ]
    entries = {entry["item_key"]: entry for entry in manifest["items"]}
    items = {item_key: deepcopy(release_1_5.items[item_key]) for item_key in entries}
    catalog = deepcopy(release_1_5.workflow_catalog)
    catalog["semantic_version"] = "1.3.0"
    restore_release_1_4_validators(catalog)
    package_node(catalog, "material.scope_review").pop("output_persistence")
    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if (
        package_checksum != RELEASE_1_3_PACKAGE_CHECKSUM
        or workflow_checksum != RELEASE_1_3_WORKFLOW_CHECKSUM
    ):
        raise AssertionError("1.3.0 release checksum differs from the published snapshot")
    return replace(
        release_1_5,
        manifest=manifest,
        items=items,
        manifest_entries=entries,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def release_1_5_3_courseware_release(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    manifest = deepcopy(source.manifest)
    manifest["semantic_version"] = "1.5.3"
    manifest["change_summary"] = RELEASE_1_5_3_CHANGE_SUMMARY
    for entry in manifest["items"]:
        if entry["item_key"] in RELEASE_1_5_3_VIDEO_ITEM_HASHES:
            entry["sha256"] = RELEASE_1_5_3_VIDEO_ITEM_HASHES[entry["item_key"]]
    entries = {entry["item_key"]: entry for entry in manifest["items"]}
    items = {item_key: deepcopy(source.items[item_key]) for item_key in entries}
    restore_video_before_1_6(items)
    for item_key, entry in entries.items():
        if canonical_json_sha256(items[item_key]) != entry["sha256"]:
            raise AssertionError(f"1.5.3 package item drifted: {item_key}")
    catalog = deepcopy(source.workflow_catalog)
    catalog["semantic_version"] = "1.5.3"
    restore_video_catalog_before_1_6(catalog)
    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if (
        package_checksum != RELEASE_1_5_3_PACKAGE_CHECKSUM
        or workflow_checksum != RELEASE_1_5_3_WORKFLOW_CHECKSUM
    ):
        raise AssertionError(
            "1.5.3 release checksum differs from the published snapshot: "
            f"package={package_checksum}, workflow={workflow_checksum}"
        )
    return replace(
        source,
        manifest=manifest,
        items=items,
        manifest_entries=entries,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def release_1_5_2_courseware_release(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    release_1_5_3 = release_1_5_3_courseware_release(source)
    manifest = deepcopy(release_1_5_3.manifest)
    manifest["semantic_version"] = "1.5.2"
    manifest["change_summary"] = RELEASE_1_5_2_CHANGE_SUMMARY
    entries = {entry["item_key"]: entry for entry in manifest["items"]}
    items = {item_key: deepcopy(release_1_5_3.items[item_key]) for item_key in entries}
    catalog = deepcopy(release_1_5_3.workflow_catalog)
    catalog["semantic_version"] = "1.5.2"
    restore_release_1_5_2_validator(catalog)
    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if (
        package_checksum != RELEASE_1_5_2_PACKAGE_CHECKSUM
        or workflow_checksum != RELEASE_1_5_2_WORKFLOW_CHECKSUM
    ):
        raise AssertionError("1.5.2 release checksum differs from the published snapshot")
    return replace(
        release_1_5_3,
        manifest=manifest,
        items=items,
        manifest_entries=entries,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def release_1_5_1_courseware_release(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    release_1_5_2 = release_1_5_2_courseware_release(source)
    manifest = deepcopy(release_1_5_2.manifest)
    manifest["semantic_version"] = "1.5.1"
    manifest["change_summary"] = RELEASE_1_5_1_CHANGE_SUMMARY
    manifest["items"] = [
        entry
        for entry in manifest["items"]
        if entry["item_key"] not in RELEASE_1_5_1_EVALUATION_ITEM_KEYS
    ]
    intro_hashes = {
        "intro.generate_options": RELEASE_1_5_1_INTRO_GENERATION_SHA256,
        "intro.generate_options.output": RELEASE_1_5_1_INTRO_OUTPUT_SHA256,
        "intro.generate_options.prompt": RELEASE_1_5_1_INTRO_PROMPT_SHA256,
    }
    for entry in manifest["items"]:
        if entry["item_key"] in intro_hashes:
            entry["sha256"] = intro_hashes[entry["item_key"]]
    entries = {entry["item_key"]: entry for entry in manifest["items"]}
    items = {item_key: deepcopy(release_1_5_2.items[item_key]) for item_key in entries}
    restore_intro_before_1_5_2(items)
    for item_key, entry in entries.items():
        if canonical_json_sha256(items[item_key]) != entry["sha256"]:
            raise AssertionError(f"1.5.1 package item drifted: {item_key}")
    catalog = deepcopy(release_1_5_2.workflow_catalog)
    catalog["semantic_version"] = "1.5.1"
    restore_release_1_5_1_validator(catalog)
    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if (
        package_checksum != RELEASE_1_5_1_PACKAGE_CHECKSUM
        or workflow_checksum != RELEASE_1_5_1_WORKFLOW_CHECKSUM
    ):
        raise AssertionError("1.5.1 release checksum differs from the published snapshot")
    return replace(
        release_1_5_2,
        manifest=manifest,
        items=items,
        manifest_entries=entries,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def release_1_5_courseware_release(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    release_1_5_1 = release_1_5_1_courseware_release(source)
    manifest = deepcopy(release_1_5_1.manifest)
    manifest["semantic_version"] = "1.5.0"
    manifest["change_summary"] = RELEASE_1_5_CHANGE_SUMMARY
    division_prompt_entry = next(
        entry
        for entry in manifest["items"]
        if entry["item_key"] == "lesson.division.generate.prompt"
    )
    division_prompt_entry["sha256"] = RELEASE_1_5_LESSON_DIVISION_PROMPT_SHA256
    division_output_entry = next(
        entry
        for entry in manifest["items"]
        if entry["item_key"] == "lesson.division.generate.output"
    )
    division_output_entry["sha256"] = RELEASE_1_5_LESSON_DIVISION_OUTPUT_SHA256
    prompt_entry = next(
        entry for entry in manifest["items"] if entry["item_key"] == "lesson_plan.generate.prompt"
    )
    prompt_entry["sha256"] = RELEASE_1_5_LESSON_PLAN_PROMPT_SHA256
    output_entry = next(
        entry for entry in manifest["items"] if entry["item_key"] == "lesson_plan.generate.output"
    )
    output_entry["sha256"] = RELEASE_1_5_LESSON_PLAN_OUTPUT_SHA256
    intro_output_entry = next(
        entry for entry in manifest["items"] if entry["item_key"] == "intro.generate_options.output"
    )
    intro_output_entry["sha256"] = RELEASE_1_5_INTRO_OUTPUT_SHA256
    entries = {entry["item_key"]: entry for entry in manifest["items"]}
    items = deepcopy(release_1_5_1.items)
    restore_lesson_division_before_1_5_1(items)
    if (
        canonical_json_sha256(items["lesson.division.generate.prompt"])
        != RELEASE_1_5_LESSON_DIVISION_PROMPT_SHA256
    ):
        raise AssertionError("1.5.0 lesson-division Prompt differs from the published snapshot")
    if (
        canonical_json_sha256(items["lesson.division.generate.output"])
        != RELEASE_1_5_LESSON_DIVISION_OUTPUT_SHA256
    ):
        raise AssertionError("1.5.0 lesson-division output differs from the published snapshot")
    prompt = items["lesson_plan.generate.prompt"]
    replacements = {
        "method": RELEASE_1_5_LESSON_PLAN_METHOD,
        "quality_gate": RELEASE_1_5_LESSON_PLAN_QUALITY_GATE,
    }
    for section in prompt["spec"]["sections"]:
        if section["section_key"] in replacements:
            section["content"] = replacements[section["section_key"]]
    if canonical_json_sha256(prompt) != RELEASE_1_5_LESSON_PLAN_PROMPT_SHA256:
        raise AssertionError("1.5.0 lesson-plan Prompt differs from the published snapshot")
    output = items["lesson_plan.generate.output"]
    restore_lesson_plan_output_before_1_5_1(items)
    if canonical_json_sha256(output) != RELEASE_1_5_LESSON_PLAN_OUTPUT_SHA256:
        raise AssertionError("1.5.0 lesson-plan output differs from the published snapshot")
    intro_output = items["intro.generate_options.output"]
    restore_intro_output_before_1_5_1(items)
    if canonical_json_sha256(intro_output) != RELEASE_1_5_INTRO_OUTPUT_SHA256:
        raise AssertionError("1.5.0 intro output differs from the published snapshot")
    catalog = deepcopy(release_1_5_1.workflow_catalog)
    catalog["semantic_version"] = "1.5.0"
    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if (
        package_checksum != RELEASE_1_5_PACKAGE_CHECKSUM
        or workflow_checksum != RELEASE_1_5_WORKFLOW_CHECKSUM
    ):
        raise AssertionError("1.5.0 release checksum differs from the published snapshot")
    return replace(
        release_1_5_1,
        manifest=manifest,
        items=items,
        manifest_entries=entries,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def release_1_4_courseware_release(
    source: BuiltinCoursewareReleaseSource,
) -> BuiltinCoursewareReleaseSource:
    release_1_5 = release_1_5_courseware_release(source)
    manifest = deepcopy(release_1_5.manifest)
    manifest["semantic_version"] = "1.4.0"
    manifest["change_summary"] = RELEASE_1_4_CHANGE_SUMMARY
    catalog = deepcopy(release_1_5.workflow_catalog)
    catalog["semantic_version"] = "1.4.0"
    restore_release_1_4_validators(catalog)
    package_checksum = canonical_json_sha256(manifest)
    workflow_checksum = hashlib.sha256(canonical_catalog_json(catalog)).hexdigest()
    if (
        package_checksum != RELEASE_1_4_PACKAGE_CHECKSUM
        or workflow_checksum != RELEASE_1_4_WORKFLOW_CHECKSUM
    ):
        raise AssertionError("1.4.0 release checksum differs from the published snapshot")
    return replace(
        release_1_5,
        manifest=manifest,
        workflow_catalog=catalog,
        package_checksum=package_checksum,
        workflow_checksum=workflow_checksum,
    )


def test_release_1_5_reconstruction_preserves_published_prompt_snapshot(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    previous = release_1_5_courseware_release(builtin_courseware_source)

    assert previous.semantic_version == "1.5.0"
    assert previous.package_checksum == RELEASE_1_5_PACKAGE_CHECKSUM
    assert previous.workflow_checksum == RELEASE_1_5_WORKFLOW_CHECKSUM
    assert (
        canonical_json_sha256(previous.items["lesson_plan.generate.prompt"])
        == RELEASE_1_5_LESSON_PLAN_PROMPT_SHA256
    )


def test_release_1_5_1_reconstruction_preserves_published_intro_snapshot(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    previous = release_1_5_1_courseware_release(builtin_courseware_source)

    assert previous.semantic_version == "1.5.1"
    assert previous.package_checksum == RELEASE_1_5_1_PACKAGE_CHECKSUM
    assert previous.workflow_checksum == RELEASE_1_5_1_WORKFLOW_CHECKSUM
    assert RELEASE_1_5_1_EVALUATION_ITEM_KEYS.isdisjoint(previous.items)
    assert (
        canonical_json_sha256(previous.items["intro.generate_options"])
        == RELEASE_1_5_1_INTRO_GENERATION_SHA256
    )
    assert (
        canonical_json_sha256(previous.items["intro.generate_options.prompt"])
        == RELEASE_1_5_1_INTRO_PROMPT_SHA256
    )
    assert (
        canonical_json_sha256(previous.items["intro.generate_options.output"])
        == RELEASE_1_5_1_INTRO_OUTPUT_SHA256
    )


def test_release_1_5_2_reconstruction_preserves_published_validator_snapshot(
    builtin_courseware_source: BuiltinCoursewareReleaseSource,
) -> None:
    previous = release_1_5_2_courseware_release(builtin_courseware_source)
    validate = package_node(previous.workflow_catalog, "intro.validate")
    refs = [
        *validate["validator_refs"],
        *validate["quality_report_persistence"]["validator_refs"],
        *previous.workflow_catalog["validator_descriptors"],
    ]
    restored = [ref for ref in refs if ref.get("key") == RELEASE_1_5_2_INTRO_SINGLE_ANCHOR["key"]]

    assert previous.semantic_version == "1.5.2"
    assert previous.package_checksum == RELEASE_1_5_2_PACKAGE_CHECKSUM
    assert previous.workflow_checksum == RELEASE_1_5_2_WORKFLOW_CHECKSUM
    assert restored == [
        RELEASE_1_5_2_INTRO_SINGLE_ANCHOR,
        RELEASE_1_5_2_INTRO_SINGLE_ANCHOR,
        {**RELEASE_1_5_2_INTRO_SINGLE_ANCHOR, "implementation_status": "contract_only"},
    ]


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
        assert source.semantic_version == "1.6.0"
        assert source.manifest["semantic_version"] == "1.6.0"
        assert source.workflow_catalog["semantic_version"] == "1.6.0"
        assert source.release_key == f"{source.package_key}@1.6.0"
        assert package_version is not None
        assert package_version.semantic_version == "1.6.0"
        assert package_version.manifest_json == source.manifest
        assert package_version.manifest_json["semantic_version"] == "1.6.0"
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
        assert current_package_version.semantic_version == source.semantic_version == "1.6.0"
        assert current_package_version.manifest_json == source.manifest
        assert current_package_version.checksum == source.package_checksum
        assert current_release.release_key == source.release_key
        assert current_release.release_key == f"{source.package_key}@1.6.0"
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
            CreateProjectRequest(title="Bound to 1.2.0", knowledge_point="One half")
        )

        assert previous.semantic_version == "1.1.0"
        assert previous.package_checksum == PREVIOUS_PACKAGE_CHECKSUM
        assert previous.workflow_checksum == PREVIOUS_WORKFLOW_CHECKSUM
        assert source.semantic_version == "1.2.0"
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


def test_release_1_3_preserves_1_2_rows_and_existing_project_binding(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    current_source = load_builtin_courseware_release(ROOT)
    source = release_1_3_courseware_release(current_source)
    previous = release_1_2_courseware_release(current_source)

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
            CreateProjectRequest(title="Bound to 1.3.0", knowledge_point="One half")
        )

        assert previous.semantic_version == "1.2.0"
        assert previous.package_checksum == RELEASE_1_2_PACKAGE_CHECKSUM
        assert previous.workflow_checksum == RELEASE_1_2_WORKFLOW_CHECKSUM
        assert source.semantic_version == "1.3.0"
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


def test_release_1_4_preserves_1_3_rows_and_existing_project_binding(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    current_source = load_builtin_courseware_release(ROOT)
    source = release_1_4_courseware_release(current_source)
    previous = release_1_3_courseware_release(current_source)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        previous_result = ContentReleasePublisher(session).publish(
            previous,
            published_by=actor.principal_id,
        )
        existing = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Bound to 1.3.0", knowledge_point="One half")
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

        assert previous.semantic_version == "1.3.0"
        assert previous.package_checksum == RELEASE_1_3_PACKAGE_CHECKSUM
        assert previous.workflow_checksum == RELEASE_1_3_WORKFLOW_CHECKSUM
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


def test_release_1_6_preserves_1_5_3_rows_and_existing_project_binding(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    source = load_builtin_courseware_release(ROOT)
    previous = release_1_5_3_courseware_release(source)

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        previous_result = ContentReleasePublisher(session).publish(
            previous,
            published_by=actor.principal_id,
        )
        existing = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Bound to 1.5.3", knowledge_point="One half")
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
            CreateProjectRequest(title="Bound to 1.6.0", knowledge_point="One half")
        )

        assert previous.semantic_version == "1.5.3"
        assert previous.package_checksum == RELEASE_1_5_3_PACKAGE_CHECKSUM
        assert previous.workflow_checksum == RELEASE_1_5_3_WORKFLOW_CHECKSUM
        assert source.semantic_version == "1.6.0"
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
