from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

import pytest
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.models import ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.assets.models import FileAssetVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.ppt_runtime_support import (
    build_ppt_service,
    seed_ppt,
    stage_gate,
    validate_pptx,
)
from workflow.node_state import NodeStatus

IMAGE_DIR_ENV = "SHANHAI_GOLDEN_PPT_IMAGE_DIR"
OUTPUT_PATH_ENV = "SHANHAI_GOLDEN_PPT_OUTPUT_PATH"


def test_real_golden_images_export_openable_approved_pptx(
    migrated_database_url: str,
) -> None:
    image_dir, output_path = _live_paths()
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage, background_dir=image_dir)
    service = build_ppt_service(factory, seeded.actor, storage)

    service.execute(seeded.assemble_node_id, request_id="issue-171-real-assemble")
    with factory() as session, session.begin():
        export_node = WorkflowRuntimeService(session, seeded.actor).create_branch_node_run(
            seeded.workflow_run_id,
            seeded.branch_run_id,
            node_key="pptx.export",
            status=NodeStatus.READY,
        )
    exported = service.execute(export_node.id, request_id="issue-171-real-export")
    assert exported.file_asset_version_id is not None

    with factory() as session:
        file_version = session.get(FileAssetVersion, exported.file_asset_version_id)
        assert file_version is not None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        storage.download_to_path(
            bucket=file_version.storage_bucket,
            key=file_version.storage_key,
            destination=output_path,
            max_bytes=100_000_000,
        )

    _assert_openable_pptx(output_path)
    _, report_id = validate_pptx(
        factory,
        seeded,
        exported.artifact_version_id,
        exported.file_asset_version_id,
    )
    stage_gate(
        factory,
        seeded,
        exported.artifact_version_id,
        exported.file_asset_version_id,
        report_id,
    )
    with factory() as session, session.begin():
        approval_id = (
            ArtifactService(session, seeded.actor)
            .review(
                exported.artifact_version_id,
                action="approve",
                comment="Approve the exact real-image golden PPTX.",
                request_id="issue-171-real-approve",
            )
            .id
        )
    _write_evidence(
        factory,
        output_path,
        exported.artifact_version_id,
        exported.file_asset_version_id,
        report_id,
        approval_id,
    )


def _live_paths() -> tuple[Path, Path]:
    image_dir = os.environ.get(IMAGE_DIR_ENV)
    output_path = os.environ.get(OUTPUT_PATH_ENV)
    if not image_dir or not output_path:
        pytest.skip(f"{IMAGE_DIR_ENV} and {OUTPUT_PATH_ENV} are required")
    resolved_images = Path(image_dir).resolve()
    resolved_output = Path(output_path).resolve()
    assert all((resolved_images / f"page-{index:02d}.png").is_file() for index in range(1, 11))
    return resolved_images, resolved_output


def _assert_openable_pptx(path: Path) -> None:
    assert path.is_file() and path.stat().st_size > 0
    with ZipFile(path) as archive:
        bad_member = archive.testzip()
        slide_names = {
            name
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        }
    assert bad_member is None
    assert len(slide_names) == 10


def _write_evidence(
    factory: sessionmaker[Session],
    output_path: Path,
    artifact_version_id: UUID,
    file_asset_version_id: UUID,
    report_id: UUID,
    approval_id: UUID,
) -> None:
    with factory() as session:
        version = session.get(ArtifactVersion, artifact_version_id)
        file_version = session.get(FileAssetVersion, file_asset_version_id)
        assert version is not None and file_version is not None
        evidence = {
            "artifact_version_id": str(version.id),
            "file_asset_version_id": str(file_version.id),
            "quality_report_id": str(report_id),
            "approval_id": str(approval_id),
            "page_count": file_version.page_count,
            "mime_type": file_version.mime_type,
            "size_bytes": file_version.byte_size,
            "sha256": file_version.sha256,
        }
    output_path.with_suffix(".evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
