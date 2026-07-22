from __future__ import annotations

from dataclasses import replace
from typing import cast
from uuid import UUID

import pytest

from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.artifacts.service import ArtifactService
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.workflows.models import NodeRun
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.ppt_runtime_scenarios import (
    create_assemble_node,
    create_export_node,
    revise_first_page_title,
)
from tests.integration.ppt_runtime_support import (
    build_ppt_service,
    seed_ppt,
    stage_gate,
    validate_pptx,
)
from workflow.node_state import NodeStatus


def test_title_revision_reexports_with_exact_backgrounds_and_new_quality_evidence(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)
    service = build_ppt_service(factory, seeded.actor, storage)
    first_assembly = service.execute(
        seeded.assemble_node_id,
        request_id="issue-170-revision-assemble-v1",
    )
    first_export_node_id = create_export_node(factory, seeded)
    first_export = service.execute(
        first_export_node_id,
        request_id="issue-170-revision-export-v1",
    )
    assert first_export.file_asset_version_id is not None
    _, old_report_id = validate_pptx(
        factory,
        seeded,
        first_export.artifact_version_id,
        first_export.file_asset_version_id,
    )

    revision = revise_first_page_title(
        factory,
        seeded,
        title="Numbers 1-5 revised title",
    )
    assert seeded.assemble_node_id in revision.stale_node_ids
    assert first_export_node_id in revision.stale_node_ids
    with factory() as session:
        first_assemble_node = session.get(NodeRun, seeded.assemble_node_id)
        first_export_node = session.get(NodeRun, first_export_node_id)
        first_assembly_version = session.get(
            ArtifactVersion,
            first_assembly.artifact_version_id,
        )
        first_export_version = session.get(ArtifactVersion, first_export.artifact_version_id)
        first_file = session.get(FileAssetVersion, first_export.file_asset_version_id)
        assert first_assemble_node is not None
        assert first_assemble_node.status == NodeStatus.STALE.value
        assert first_export_node is not None
        assert first_export_node.status == NodeStatus.STALE.value
        assert first_assembly_version is not None and first_export_version is not None
        assert first_file is not None

    second_assemble_node_id = create_assemble_node(factory, seeded)
    revised_seed = replace(
        seeded,
        page_specs_version_id=revision.version_id,
        assemble_node_id=second_assemble_node_id,
    )
    second_assembly = service.execute(
        second_assemble_node_id,
        request_id="issue-170-revision-assemble-v2",
    )
    second_export_node_id = create_export_node(factory, revised_seed)
    second_export = service.execute(
        second_export_node_id,
        request_id="issue-170-revision-export-v2",
    )
    assert second_export.file_asset_version_id is not None

    with factory() as session:
        first_assembly_version = cast(
            ArtifactVersion,
            session.get(ArtifactVersion, first_assembly.artifact_version_id),
        )
        second_assembly_version = cast(
            ArtifactVersion,
            session.get(ArtifactVersion, second_assembly.artifact_version_id),
        )
        first_export_version = cast(
            ArtifactVersion,
            session.get(ArtifactVersion, first_export.artifact_version_id),
        )
        second_export_version = cast(
            ArtifactVersion,
            session.get(ArtifactVersion, second_export.artifact_version_id),
        )
        first_file = cast(
            FileAssetVersion,
            session.get(FileAssetVersion, first_export.file_asset_version_id),
        )
        second_file = cast(
            FileAssetVersion,
            session.get(FileAssetVersion, second_export.file_asset_version_id),
        )
        first_assembly_artifact = cast(
            Artifact,
            session.get(Artifact, first_assembly_version.artifact_id),
        )
        second_assembly_artifact = cast(
            Artifact,
            session.get(Artifact, second_assembly_version.artifact_id),
        )
        first_export_artifact = cast(
            Artifact,
            session.get(Artifact, first_export_version.artifact_id),
        )
        second_export_artifact = cast(
            Artifact,
            session.get(Artifact, second_export_version.artifact_id),
        )
        assert first_assembly_artifact.id == second_assembly_artifact.id
        assert first_export_artifact.id == second_export_artifact.id
        assert first_assembly_version.id != second_assembly_version.id
        assert first_export_version.id != second_export_version.id
        assert first_file.file_asset_id == second_file.file_asset_id
        assert first_file.id != second_file.id
        assert first_file.sha256 != second_file.sha256
        revised_title = next(
            element["text"]
            for element in second_assembly_version.content_json["pages"][0]["elements"]
            if element["element_key"] == "PPT-TEXT-01"
        )
        assert revised_title == "Numbers 1-5 revised title"
        assert _background_version_ids(first_assembly_version) == _background_version_ids(
            second_assembly_version
        )
        assert _background_hashes(first_assembly_version) == _background_hashes(
            second_assembly_version
        )
        background_assets = list(
            session.query(FileAsset)
            .filter(FileAsset.current_version_id.in_(seeded.background_version_ids))
            .all()
        )
        assert len(background_assets) == 10
        assert all(asset.status == "active" for asset in background_assets)

    with factory() as session:
        with pytest.raises(ApiError) as caught:
            with session.begin():
                ArtifactService(session, revised_seed.actor).review(
                    second_export.artifact_version_id,
                    action="approve",
                    comment="Old report must not unlock revised PPTX.",
                    request_id="issue-170-revision-old-report",
                )
        assert caught.value.code == "ARTIFACT_QUALITY_REQUIRED"

    _, new_report_id = validate_pptx(
        factory,
        revised_seed,
        second_export.artifact_version_id,
        second_export.file_asset_version_id,
    )
    assert new_report_id != old_report_id
    gate_node_id = stage_gate(
        factory,
        revised_seed,
        second_export.artifact_version_id,
        second_export.file_asset_version_id,
        new_report_id,
    )
    with factory() as session, session.begin():
        approval = ArtifactService(session, revised_seed.actor).review(
            second_export.artifact_version_id,
            action="approve",
            comment="Approve revised exact PPTX.",
            request_id="issue-170-revision-approve",
        )

    with factory() as session:
        gate_node = session.get(NodeRun, gate_node_id)
        export_artifact = session.get(Artifact, second_export_version.artifact_id)
        assert gate_node is not None and gate_node.status == NodeStatus.APPROVED.value
        assert export_artifact is not None
        assert export_artifact.current_approved_version_id == second_export.artifact_version_id
        assert approval.quality_evidence_json["report_id"] == str(new_report_id)


def _background_version_ids(version: ArtifactVersion) -> tuple[UUID, ...]:
    return tuple(
        UUID(page["background_file_asset_version_id"]) for page in version.content_json["pages"]
    )


def _background_hashes(version: ArtifactVersion) -> tuple[str, ...]:
    return tuple(page["background_sha256"] for page in version.content_json["pages"])
