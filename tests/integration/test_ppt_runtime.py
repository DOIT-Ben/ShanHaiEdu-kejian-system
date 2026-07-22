from __future__ import annotations

from dataclasses import replace
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import func, select

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.assets.models import FileAssetVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.ids import new_uuid7
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.node_execution.deterministic_router import build_deterministic_node_executor
from apps.api.ppt_runtime.contracts import PptRuntimeError
from apps.api.workflows.models import NodeRun
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.ppt_runtime_support import (
    build_ppt_service,
    count_for_node,
    seed_ppt,
    stage_gate,
    validate_pptx,
)
from workflow.node_state import NodeStatus


def test_published_executor_router_runs_ppt_assembly_from_fixed_binding(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)
    executor = build_deterministic_node_executor(
        factory,
        seeded.actor,
        storage,
        storage_bucket="shanhaiedu",
    )

    result = executor.execute(
        seeded.assemble_node_id,
        request_id="issue-170-published-executor-router",
    )

    with factory() as session:
        version = session.get(ArtifactVersion, result.artifact_version_id)
        node = session.get(NodeRun, seeded.assemble_node_id)
        assert version is not None and version.content_json["page_count"] == 10
        assert node is not None and node.status == NodeStatus.APPROVED.value


def test_golden_ppt_runs_to_exact_file_quality_and_approval(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)
    service = build_ppt_service(factory, seeded.actor, storage)

    assembled = service.execute(
        seeded.assemble_node_id,
        request_id="issue-170-pages-assemble",
    )
    with factory() as session, session.begin():
        export_node = WorkflowRuntimeService(session, seeded.actor).create_branch_node_run(
            seeded.workflow_run_id,
            seeded.branch_run_id,
            node_key="pptx.export",
            status=NodeStatus.READY,
        )
    exported = service.execute(export_node.id, request_id="issue-170-pptx-export")

    assert assembled.file_asset_version_id is None
    assert exported.file_asset_version_id is not None
    with factory() as session:
        assembly_version = session.get(ArtifactVersion, assembled.artifact_version_id)
        assembly_artifact = session.get(
            Artifact,
            assembly_version.artifact_id if assembly_version is not None else None,
        )
        export_version = session.get(ArtifactVersion, exported.artifact_version_id)
        export_artifact = session.get(
            Artifact,
            export_version.artifact_id if export_version is not None else None,
        )
        file_version = session.get(FileAssetVersion, exported.file_asset_version_id)
        assemble_node = session.get(NodeRun, seeded.assemble_node_id)
        persisted_export_node = session.get(NodeRun, export_node.id)

        assert assembly_version is not None and assembly_artifact is not None
        assert export_version is not None and export_artifact is not None
        assert file_version is not None
        assert assemble_node is not None and assemble_node.status == NodeStatus.APPROVED.value
        assert persisted_export_node is not None
        assert persisted_export_node.status == NodeStatus.REVIEW_REQUIRED.value
        assert assembly_artifact.status == "approved"
        assert assembly_version.source_kind == "system"
        assert assembly_version.prompt_snapshot_id is None
        assert assembly_version.content_json["page_count"] == 10
        assert [page["page_key"] for page in assembly_version.content_json["pages"]] == [
            f"PAGE-{index:02d}" for index in range(1, 11)
        ]
        assert {
            UUID(page["background_file_asset_version_id"])
            for page in assembly_version.content_json["pages"]
        } == set(seeded.background_version_ids)
        assert export_version.source_kind == "system"
        assert export_artifact.status == "in_review"
        assert export_version.content_json["file_asset_version_id"] == str(file_version.id)
        assert export_version.content_json["mime_type"] == file_version.mime_type
        assert export_version.content_json["size_bytes"] == file_version.byte_size
        assert export_version.content_json["sha256"] == file_version.sha256
        assert export_version.content_json["page_count"] == 10
        assert file_version.byte_size > 0
        assert file_version.mime_type == (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        assert file_version.sha256 != assembly_version.content_hash
        assert count_for_node(session, GenerationAttempt, seeded.assemble_node_id) == 1
        assert count_for_node(session, GenerationAttempt, export_node.id) == 1
        assert count_for_node(session, UsageRecord, seeded.assemble_node_id) == 1
        assert count_for_node(session, UsageRecord, export_node.id) == 1
        storage_metadata = storage.stat(
            bucket=file_version.storage_bucket,
            key=file_version.storage_key,
        )
        assert storage_metadata.size_bytes == file_version.byte_size
        assert storage_metadata.sha256 == file_version.sha256

    validate_node_id, report_id = validate_pptx(
        factory,
        seeded,
        exported.artifact_version_id,
        exported.file_asset_version_id,
    )
    gate_node_id = stage_gate(
        factory,
        seeded,
        exported.artifact_version_id,
        exported.file_asset_version_id,
        report_id,
    )
    with factory() as session, session.begin():
        approval = ArtifactService(session, seeded.actor).review(
            exported.artifact_version_id,
            action="approve",
            comment="Approve the exact golden PPTX.",
            request_id="issue-170-approve-pptx",
        )

    with factory() as session:
        validate_node = session.get(NodeRun, validate_node_id)
        gate_node = session.get(NodeRun, gate_node_id)
        export_artifact = session.get(
            Artifact,
            cast(
                ArtifactVersion, session.get(ArtifactVersion, exported.artifact_version_id)
            ).artifact_id,
        )
        record = session.get(Approval, approval.id)
        report = session.get(ArtifactQualityReport, report_id)
        assert validate_node is not None and validate_node.status == NodeStatus.APPROVED.value
        assert gate_node is not None and gate_node.status == NodeStatus.APPROVED.value
        assert export_artifact is not None
        assert export_artifact.current_approved_version_id == exported.artifact_version_id
        assert record is not None and report is not None
        assert record.quality_evidence_json["report_id"] == str(report.id)
        assert record.quality_evidence_json["source_type"] == "asset"
        assert record.quality_evidence_json["source_file_asset_version_id"] == str(
            exported.file_asset_version_id
        )
        assert record.quality_evidence_json["source_content_hash"] == report.source_content_hash


def test_duplicate_export_reuses_one_artifact_file_attempt_and_usage(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)
    service = build_ppt_service(factory, seeded.actor, storage)
    service.execute(seeded.assemble_node_id, request_id="issue-170-assemble-once")
    with factory() as session, session.begin():
        export_node = WorkflowRuntimeService(session, seeded.actor).create_branch_node_run(
            seeded.workflow_run_id,
            seeded.branch_run_id,
            node_key="pptx.export",
            status=NodeStatus.READY,
        )

    first = service.execute(export_node.id, request_id="issue-170-export-replay")
    replay = service.execute(export_node.id, request_id="issue-170-export-replay")

    assert replay == first
    with factory() as session:
        assert count_for_node(session, GenerationAttempt, export_node.id) == 1
        assert count_for_node(session, UsageRecord, export_node.id) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactVersion)
                .where(ArtifactVersion.source_node_run_id == export_node.id)
            )
            == 1
        )
        assert session.get(FileAssetVersion, first.file_asset_version_id) is not None


def test_cross_tenant_execution_fails_before_attempt_or_storage_write(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)
    baseline_objects = storage.object_count
    outsider = replace(seeded.actor, organization_id=new_uuid7())

    with pytest.raises(PptRuntimeError):
        build_ppt_service(factory, outsider, storage).execute(
            seeded.assemble_node_id,
            request_id="issue-170-cross-tenant",
        )

    with factory() as session:
        assert count_for_node(session, GenerationAttempt, seeded.assemble_node_id) == 0
        assert count_for_node(session, UsageRecord, seeded.assemble_node_id) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactVersion)
                .where(ArtifactVersion.source_node_run_id == seeded.assemble_node_id)
            )
            == 0
        )
    assert storage.object_count == baseline_objects
