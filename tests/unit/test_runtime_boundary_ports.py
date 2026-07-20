from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from uuid import uuid4

import pytest

from apps.api.artifacts.domain import ArtifactInvariantError, ArtifactRelationType
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
    scope = {
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
    scope["keys"].append("LESSON-002")
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
        node_run_id=uuid4(),
        context_snapshot_id=uuid4(),
        prompt_snapshot_id=uuid4(),
        artifact_key="lesson.01.plan",
        artifact_type="lesson_plan",
        branch_key="lesson_plan",
        content_definition_version_id=uuid4(),
        content={},
        request_id="req-generated-artifact",
        relations=[relation],  # type: ignore[arg-type]
    )
    assert write.relations == (relation,)


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
