from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.artifacts.models import ArtifactVersion
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.ppt_rendering.models import AssemblyManifest, AssemblyRequest, PptxFileFact
from apps.api.ppt_rendering.service import assemble_pages, export_pptx
from apps.api.ppt_runtime.contracts import PptRuntimeError
from apps.api.ppt_runtime.service import PptRuntimeService
from apps.api.ppt_runtime.sqlalchemy import SqlAlchemyPptRuntimeTransactionFactory
from apps.api.uploads.storage import ObjectMetadata, ObjectStorageError
from apps.api.workflows.models import NodeRun
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.ppt_runtime_scenarios import create_export_node
from tests.integration.ppt_runtime_support import (
    build_ppt_service,
    count_for_node,
    seed_ppt,
)
from workflow.node_state import NodeStatus


class _CancelAfterExportRenderer:
    def __init__(self, cancel: Callable[[], None]) -> None:
        self._cancel = cancel

    def assemble_pages(self, request: AssemblyRequest) -> AssemblyManifest:
        return assemble_pages(request)

    def export_pptx(self, request: AssemblyRequest) -> PptxFileFact:
        result = export_pptx(request)
        self._cancel()
        return result


class _FailOncePublishStorage(FakeObjectStorage):
    def __init__(self, phase: Literal["staging_put", "final_copy"]) -> None:
        super().__init__()
        self._phase = phase
        self._armed = False

    def arm(self) -> None:
        self._armed = True

    def put_bytes(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        media_type: str,
    ) -> ObjectMetadata:
        metadata = super().put_bytes(
            bucket=bucket,
            key=key,
            payload=payload,
            media_type=media_type,
        )
        if self._armed and self._phase == "staging_put" and key.endswith("/staging.pptx"):
            self._armed = False
            raise ObjectStorageError("injected staging upload failure")
        return metadata

    def copy(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
    ) -> ObjectMetadata:
        metadata = super().copy(
            source_bucket=source_bucket,
            source_key=source_key,
            destination_bucket=destination_bucket,
            destination_key=destination_key,
        )
        if self._armed and self._phase == "final_copy":
            self._armed = False
            raise ObjectStorageError("injected final copy acknowledgement failure")
        return metadata


class _FailOnceDownloadStorage(FakeObjectStorage):
    def __init__(self) -> None:
        super().__init__()
        self._failed_key: tuple[str, str] | None = None

    def fail_once(self, *, bucket: str, key: str) -> None:
        self._failed_key = (bucket, key)

    def download_to_path(
        self,
        *,
        bucket: str,
        key: str,
        destination: Path,
        max_bytes: int,
    ) -> ObjectMetadata:
        if self._failed_key == (bucket, key):
            self._failed_key = None
            raise ObjectStorageError("injected single-page download failure")
        return super().download_to_path(
            bucket=bucket,
            key=key,
            destination=destination,
            max_bytes=max_bytes,
        )


def test_pre_cancel_terminalizes_without_attempt_or_artifact(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)
    with factory() as session, session.begin():
        runtime = WorkflowRuntimeService(session, seeded.actor)
        runtime.transition_node(seeded.assemble_node_id, NodeStatus.QUEUED)
        runtime.transition_node(
            seeded.assemble_node_id,
            NodeStatus.CANCEL_REQUESTED,
        )

    with pytest.raises(PptRuntimeError) as caught:
        build_ppt_service(factory, seeded.actor, storage).execute(
            seeded.assemble_node_id,
            request_id="issue-170-pre-cancel",
        )

    assert caught.value.code == "PPT_RUNTIME_CANCEL_REQUESTED"
    with factory() as session:
        node = session.get(NodeRun, seeded.assemble_node_id)
        assert node is not None and node.status == NodeStatus.CANCELLED.value
        assert count_for_node(session, GenerationAttempt, node.id) == 0
        assert count_for_node(session, UsageRecord, node.id) == 0
        assert _artifact_count(session, node.id) == 0
    assert storage.object_count == 10


def test_cancel_after_render_cleans_object_and_cancels_exact_attempt(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)
    build_ppt_service(factory, seeded.actor, storage).execute(
        seeded.assemble_node_id,
        request_id="issue-170-cancel-assemble",
    )
    export_node_id = create_export_node(factory, seeded)

    def cancel() -> None:
        with factory() as session, session.begin():
            WorkflowRuntimeService(session, seeded.actor).transition_node(
                export_node_id,
                NodeStatus.CANCEL_REQUESTED,
            )

    service = PptRuntimeService(
        SqlAlchemyPptRuntimeTransactionFactory(factory, seeded.actor),
        storage,
        storage_bucket="shanhaiedu",
        renderer=_CancelAfterExportRenderer(cancel),
    )
    with pytest.raises(PptRuntimeError) as caught:
        service.execute(export_node_id, request_id="issue-170-cancel-after-render")

    assert caught.value.code == "PPT_RUNTIME_CANCEL_REQUESTED"
    with factory() as session:
        node = session.get(NodeRun, export_node_id)
        attempt = session.scalar(
            select(GenerationAttempt).where(GenerationAttempt.node_run_id == export_node_id)
        )
        assert node is not None and node.status == NodeStatus.CANCELLED.value
        assert attempt is not None and attempt.status == "cancelled"
        assert count_for_node(session, UsageRecord, export_node_id) == 1
        assert _artifact_count(session, export_node_id) == 0
        assert _pptx_file_count(session) == 0
    assert storage.object_count == 10


@pytest.mark.parametrize(
    "fault_stage", ["after_attempt", "after_file_asset", "after_artifact", "after_terminal"]
)
def test_any_t2_fault_rolls_back_database_and_compensates_published_object(
    migrated_database_url: str,
    fault_stage: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)
    build_ppt_service(factory, seeded.actor, storage).execute(
        seeded.assemble_node_id,
        request_id=f"issue-170-t2-assemble-{fault_stage}",
    )
    export_node_id = create_export_node(factory, seeded)

    def fail(stage: str) -> None:
        if stage == fault_stage:
            raise RuntimeError(f"fault injected at {stage}")

    service = PptRuntimeService(
        SqlAlchemyPptRuntimeTransactionFactory(
            factory,
            seeded.actor,
            fault_injector=fail,
        ),
        storage,
        storage_bucket="shanhaiedu",
    )
    with pytest.raises(PptRuntimeError):
        service.execute(export_node_id, request_id=f"issue-170-t2-{fault_stage}")

    with factory() as session:
        node = session.get(NodeRun, export_node_id)
        attempt = session.scalar(
            select(GenerationAttempt).where(GenerationAttempt.node_run_id == export_node_id)
        )
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert attempt is not None and attempt.status == "failed"
        assert count_for_node(session, UsageRecord, export_node_id) == 1
        assert _artifact_count(session, export_node_id) == 0
        assert _pptx_file_count(session) == 0
    assert storage.object_count == 10


@pytest.mark.parametrize("phase", ["staging_put", "final_copy"])
def test_upload_failure_cleans_staging_and_final_objects(
    migrated_database_url: str,
    phase: Literal["staging_put", "final_copy"],
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = _FailOncePublishStorage(phase)
    seeded = seed_ppt(factory, storage)
    build_ppt_service(factory, seeded.actor, storage).execute(
        seeded.assemble_node_id,
        request_id=f"issue-170-upload-assemble-{phase}",
    )
    export_node_id = create_export_node(factory, seeded)
    storage.arm()

    with pytest.raises(PptRuntimeError):
        build_ppt_service(factory, seeded.actor, storage).execute(
            export_node_id,
            request_id=f"issue-170-upload-{phase}",
        )

    with factory() as session:
        node = session.get(NodeRun, export_node_id)
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert _artifact_count(session, export_node_id) == 0
        assert _pptx_file_count(session) == 0
    assert storage.object_count == 10


def test_failed_final_copy_recovers_once_without_orphan_object(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = _FailOncePublishStorage("final_copy")
    seeded = seed_ppt(factory, storage)
    build_ppt_service(factory, seeded.actor, storage).execute(
        seeded.assemble_node_id,
        request_id="issue-170-recovery-assemble",
    )
    export_node_id = create_export_node(factory, seeded)
    storage.arm()
    service = build_ppt_service(factory, seeded.actor, storage)

    with pytest.raises(PptRuntimeError):
        service.execute(export_node_id, request_id="issue-170-recovery-export")
    recovered = service.execute(export_node_id, request_id="issue-170-recovery-export")

    assert recovered.file_asset_version_id is not None
    with factory() as session:
        node = session.get(NodeRun, export_node_id)
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.node_run_id == export_node_id)
                .order_by(GenerationAttempt.attempt_no)
            )
        )
        assert node is not None and node.status == NodeStatus.REVIEW_REQUIRED.value
        assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]
        assert count_for_node(session, UsageRecord, export_node_id) == 2
        assert _artifact_count(session, export_node_id) == 1
        assert _pptx_file_count(session) == 1
    assert storage.object_count == 11


def test_single_page_download_failure_reuses_frozen_exact_backgrounds_on_retry(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = _FailOnceDownloadStorage()
    seeded = seed_ppt(factory, storage)
    target_version_id = seeded.background_version_ids[4]
    with factory() as session:
        target = session.get(FileAssetVersion, target_version_id)
        assert target is not None
        storage.fail_once(bucket=target.storage_bucket, key=target.storage_key)
    service = build_ppt_service(factory, seeded.actor, storage)

    with pytest.raises(PptRuntimeError):
        service.execute(seeded.assemble_node_id, request_id="issue-170-page-retry")
    recovered = service.execute(seeded.assemble_node_id, request_id="issue-170-page-retry")

    with factory() as session:
        version = session.get(ArtifactVersion, recovered.artifact_version_id)
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.node_run_id == seeded.assemble_node_id)
                .order_by(GenerationAttempt.attempt_no)
            )
        )
        assert version is not None
        assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]
        assert {
            page["background_file_asset_version_id"] for page in version.content_json["pages"]
        } == {str(value) for value in seeded.background_version_ids}
        assert count_for_node(session, UsageRecord, seeded.assemble_node_id) == 2
    assert storage.object_count == 10


def _artifact_count(session: Session, node_run_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(ArtifactVersion)
            .where(ArtifactVersion.source_node_run_id == node_run_id)
        )
        or 0
    )


def _pptx_file_count(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(FileAssetVersion)
            .join(FileAsset, FileAsset.id == FileAssetVersion.file_asset_id)
            .where(FileAsset.asset_kind == "pptx")
        )
        or 0
    )
