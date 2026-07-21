from __future__ import annotations

from dataclasses import fields, replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from apps.api.artifacts.domain import ArtifactInvariantError, ArtifactRelationType
from apps.api.ids import new_uuid7
from apps.api.runtime_boundary.ports import (
    ArtifactPort,
    ArtifactWriteResult,
    AssetPort,
    CreationPackageItemSpec,
    CreationPackagePort,
    CreationPackageReferenceAssetSpec,
    CreationPackageSpec,
    CreationPackageWriteResult,
    GeneratedArtifactRelation,
    GeneratedArtifactWrite,
    ModelInvocationPort,
    PromptSnapshotPort,
    RuntimeDefinitionReader,
    WorkflowExecutionPort,
)


def _generated_write() -> GeneratedArtifactWrite:
    return GeneratedArtifactWrite(
        project_id=uuid4(),
        lesson_unit_id=None,
        node_run_id=uuid4(),
        context_snapshot_id=uuid4(),
        prompt_snapshot_id=uuid4(),
        artifact_key="lesson.01.plan",
        artifact_type="lesson_plan",
        branch_key="lesson_plan",
        content_definition_version_id=uuid4(),
        content={},
        request_id="req-generated-artifact",
    )


def _package_item(*, position: int = 1) -> CreationPackageItemSpec:
    return CreationPackageItemSpec(
        item_key=f"item-{position}",
        position=position,
        title=f"Item {position}",
        business_prompt="Create a classroom-safe visual.",
        prompt={},
        reference_assets=(),
        output_spec={},
        target_slot_key=f"ppt.page-{position}.main-visual",
        consistency_key=None,
    )


def test_runtime_boundary_exposes_only_the_minimum_issue_89_ports() -> None:
    expected_methods = {
        RuntimeDefinitionReader: {"resolve"},
        WorkflowExecutionPort: {"require_context", "transition"},
        ArtifactPort: {"list_context_versions", "persist_generated"},
        AssetPort: {"list_context_items"},
        PromptSnapshotPort: {"freeze"},
        ModelInvocationPort: {"generate_text"},
        CreationPackagePort: {"publish"},
    }

    for port, methods in expected_methods.items():
        assert port.__dict__.get("_is_protocol") is True
        assert methods <= set(port.__dict__)


def test_generated_artifact_write_carries_immutable_relation_declarations() -> None:
    scope: dict[str, object] = {
        "mode": "keyed",
        "selector": "lesson_key",
        "keys": ["LESSON-001"],
    }
    relation = GeneratedArtifactRelation(
        from_artifact_version_id=uuid4(),
        relation_type=ArtifactRelationType.DERIVES_FROM,
        binding_key="lesson-scope",
        impact_scope=scope,
    )
    keys = cast(list[str], scope["keys"])
    keys.append("LESSON-002")
    assert relation.from_artifact_version_id
    assert relation.relation_type is ArtifactRelationType.DERIVES_FROM
    assert relation.impact_scope == {
        "mode": "keyed",
        "selector": "lesson_key",
        "keys": ("LESSON-001",),
    }
    with pytest.raises(TypeError):
        relation.impact_scope["mode"] = "all"  # type: ignore[index]
    assert "to_artifact_version_id" not in {field.name for field in fields(relation)}
    assert "relations" in {field.name for field in fields(GeneratedArtifactWrite)}

    write = GeneratedArtifactWrite(
        project_id=uuid4(),
        lesson_unit_id=None,
        node_run_id=uuid4(),
        context_snapshot_id=uuid4(),
        prompt_snapshot_id=uuid4(),
        artifact_key="lesson.01.plan",
        artifact_type="lesson_plan",
        branch_key="lesson_plan",
        content_definition_version_id=uuid4(),
        content={"nested": {"value": 1}},
        request_id="req-generated-artifact",
        relations=[relation],  # type: ignore[arg-type]
    )
    assert write.relations == (relation,)
    with pytest.raises(TypeError):
        dict.__setitem__(write.content, "forged", True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        dict.__setitem__(write.content["nested"], "value", 2)  # type: ignore[arg-type]

    item = replace(_package_item(), output_spec={"size": {"width": 1920}})
    with pytest.raises(TypeError):
        dict.__setitem__(item.output_spec, "forged", True)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        dict.__setitem__(item.output_spec["size"], "width", 1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_key", ""),
        ("artifact_type", ""),
        ("branch_key", ""),
        ("request_id", ""),
        ("content", "not-an-object"),
    ],
)
def test_generated_artifact_write_rejects_invalid_port_values(field: str, value: object) -> None:
    with pytest.raises(ArtifactInvariantError):
        replace(_generated_write(), **{field: value})


@pytest.mark.parametrize(
    ("relation_type", "binding_key", "impact_scope"),
    [
        ("derives_from", "lesson-scope", {"mode": "all"}),
        (ArtifactRelationType.DERIVES_FROM, " ", {"mode": "all"}),
        (ArtifactRelationType.DERIVES_FROM, "x" * 161, {"mode": "all"}),
        (ArtifactRelationType.DERIVES_FROM, "lesson-scope", {}),
        (
            ArtifactRelationType.DERIVES_FROM,
            "lesson-scope",
            {"mode": "keyed", "selector": "unknown", "keys": ["LESSON-001"]},
        ),
    ],
)
def test_generated_relation_rejects_invalid_runtime_values(
    relation_type: object,
    binding_key: str,
    impact_scope: dict[str, object],
) -> None:
    with pytest.raises(ArtifactInvariantError):
        GeneratedArtifactRelation(
            from_artifact_version_id=uuid4(),
            relation_type=relation_type,  # type: ignore[arg-type]
            binding_key=binding_key,
            impact_scope=impact_scope,
        )


def test_generated_relation_rejects_invalid_source_id() -> None:
    with pytest.raises(ArtifactInvariantError, match="source version"):
        GeneratedArtifactRelation(
            from_artifact_version_id="not-a-uuid",  # type: ignore[arg-type]
            relation_type=ArtifactRelationType.DERIVES_FROM,
            binding_key="lesson-scope",
            impact_scope={"mode": "all"},
        )


def test_generated_relation_accepts_canonical_uuid7_source_id() -> None:
    source_id = new_uuid7()

    relation = GeneratedArtifactRelation(
        from_artifact_version_id=source_id,
        relation_type=ArtifactRelationType.DERIVES_FROM,
        binding_key="lesson-scope",
        impact_scope={"mode": "all"},
    )

    assert relation.from_artifact_version_id == source_id


@pytest.mark.parametrize("value", [float("nan"), b"bytes", uuid4(), {"value"}])
def test_generated_artifact_write_rejects_non_json_content(value: object) -> None:
    with pytest.raises(ArtifactInvariantError, match="JSON"):
        GeneratedArtifactWrite(
            project_id=uuid4(),
            lesson_unit_id=None,
            node_run_id=uuid4(),
            context_snapshot_id=uuid4(),
            prompt_snapshot_id=uuid4(),
            artifact_key="lesson.01.plan",
            artifact_type="lesson_plan",
            branch_key="lesson_plan",
            content={"value": value},
            content_definition_version_id=uuid4(),
            request_id="req-json",
        )


def test_creation_package_item_rejects_nonsemantic_slot_and_duplicate_asset_ids() -> None:
    with pytest.raises(ArtifactInvariantError, match="target slot"):
        replace(_package_item(), target_slot_key="../../foreign-project")

    asset_id = uuid4()
    assets = (
        CreationPackageReferenceAssetSpec(asset_id, "style"),
        CreationPackageReferenceAssetSpec(asset_id, "character"),
    )
    with pytest.raises(ArtifactInvariantError, match="asset IDs"):
        replace(_package_item(), reference_assets=assets)


def test_creation_package_spec_enforces_artifact_key_and_item_limit() -> None:
    artifact_version_id = uuid4()
    common = {
        "project_id": uuid4(),
        "workflow_run_id": uuid4(),
        "node_run_id": uuid4(),
        "lesson_unit_id": None,
        "artifact_version_id": artifact_version_id,
        "context_snapshot_id": uuid4(),
        "prompt_snapshot_id": uuid4(),
        "package_key": f"ppt-body:{artifact_version_id}",
        "package_type": "presentation",
        "items": (_package_item(),),
        "target_rules": {
            "replace_modes": ["reject_if_occupied"],
            "allow_download": True,
        },
        "request_id": "req-package",
    }
    package = CreationPackageSpec(**common)  # type: ignore[arg-type]

    with pytest.raises(ArtifactInvariantError, match="bound to its artifact"):
        replace(package, package_key="unrelated-key")
    with pytest.raises(ArtifactInvariantError, match="items are invalid"):
        replace(
            package,
            items=tuple(_package_item(position=index) for index in range(1, 102)),
        )


@pytest.mark.parametrize(
    ("result_type", "kwargs"),
    [
        (
            CreationPackageWriteResult,
            {
                "creation_package_id": "not-a-uuid",
                "status": "ready",
                "content_hash": "a" * 64,
            },
        ),
        (
            CreationPackageWriteResult,
            {
                "creation_package_id": uuid4(),
                "status": "unknown",
                "content_hash": "a" * 64,
            },
        ),
        (
            ArtifactWriteResult,
            {
                "artifact_id": uuid4(),
                "artifact_version_id": uuid4(),
                "content_hash": "not-a-hash",
                "project_id": uuid4(),
                "node_run_id": uuid4(),
                "context_snapshot_id": uuid4(),
                "prompt_snapshot_id": uuid4(),
                "artifact_key": "artifact",
                "artifact_type": "lesson_plan",
                "branch_key": "lesson_plan",
                "lesson_unit_id": None,
                "content_definition_version_id": uuid4(),
            },
        ),
    ],
)
def test_write_results_reject_invalid_adapter_values(
    result_type: type[object], kwargs: dict[str, object]
) -> None:
    with pytest.raises(ArtifactInvariantError):
        result_type(**kwargs)


def test_backend_boundary_document_records_ports_and_live_size_baseline() -> None:
    document = (
        Path(__file__).resolve().parents[2] / "docs/backend/07_后端实现边界与维护门禁.md"
    ).read_text(encoding="utf-8")

    for name in (
        "RuntimeDefinitionReader",
        "WorkflowExecutionPort",
        "ArtifactPort",
        "AssetPort",
        "PromptSnapshotPort",
        "ModelInvocationPort",
        "CreationPackagePort",
    ):
        assert f"`{name}`" in document
    assert "4 个生产文件超过 400 行" in document
    assert "24 个生产函数超过 60 行" in document
