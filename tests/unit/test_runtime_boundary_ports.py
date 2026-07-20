from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from uuid import uuid4

from apps.api.artifacts.domain import ArtifactRelationType
from apps.api.runtime_boundary.ports import (
    ArtifactPort,
    AssetPort,
    CreationPackagePort,
    GeneratedArtifactRelation,
    GeneratedArtifactWrite,
    ModelInvocationPort,
    PromptSnapshotPort,
    RuntimeDefinitionReader,
    WorkflowExecutionPort,
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
    relation = GeneratedArtifactRelation(
        from_artifact_version_id=uuid4(),
        relation_type=ArtifactRelationType.DERIVES_FROM,
        binding_key="lesson-scope",
        impact_scope={"mode": "all"},
    )
    assert relation.from_artifact_version_id
    assert relation.relation_type is ArtifactRelationType.DERIVES_FROM
    assert "to_artifact_version_id" not in {field.name for field in fields(relation)}
    assert "relations" in {field.name for field in fields(GeneratedArtifactWrite)}


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
