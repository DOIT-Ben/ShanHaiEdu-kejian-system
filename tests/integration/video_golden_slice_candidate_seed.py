from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.models import ArtifactVersion
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
)
from apps.api.assets.project_service import ProjectAssetService
from apps.api.creation.models import (
    CreationBatch,
    CreationItem,
    CreationPackage,
    CreationPackageItem,
    CreationPromptVersion,
    GenerationResult,
)
from apps.api.database import utc_now
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowRun
from tests.integration.video_golden_slice_project_seed import VideoProjectSeed


@dataclass(frozen=True, slots=True)
class CompletedVideoCandidate:
    result_id: UUID
    file_asset_version_id: UUID
    target_slot_key: str


def seed_completed_candidate(
    session: Session,
    seeded: VideoProjectSeed,
    *,
    lesson_index: int,
    mime_type: str = "video/mp4",
) -> CompletedVideoCandidate:
    lesson = seeded.lessons[lesson_index]
    run = session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.project_id == seeded.project_id,
            WorkflowRun.status == "active",
        )
    )
    assert run is not None
    branch = session.scalar(
        select(BranchRun).where(
            BranchRun.workflow_run_id == run.id,
            BranchRun.lesson_unit_id == lesson.lesson_id,
            BranchRun.branch_key == "video",
        )
    )
    source_version = session.get(ArtifactVersion, lesson.intro_artifact_version_id)
    assert branch is not None and source_version is not None
    now = utc_now()
    node = session.scalar(
        select(NodeRun).where(
            NodeRun.branch_run_id == branch.id,
            NodeRun.node_key == "video.shots.generate",
            NodeRun.run_no == 1,
        )
    )
    if node is None:
        node = NodeRun(
            id=new_uuid7(),
            organization_id=seeded.actor.organization_id,
            workflow_run_id=run.id,
            branch_run_id=branch.id,
            node_key="video.shots.generate",
            run_no=1,
            status="review_required",
            trigger_type="manual",
            automation_policy_snapshot_json=run.automation_policy_snapshot_json,
            started_at=now,
            finished_at=now,
            created_by=seeded.actor.principal_id,
            updated_by=seeded.actor.principal_id,
        )
        session.add(node)
    else:
        node.status = "review_required"
        node.started_at = node.started_at or now
        node.finished_at = now
        node.updated_by = seeded.actor.principal_id
    session.flush()
    target_slot_key = f"lesson.{lesson_index + 1:02d}.video.intro.selected"
    ProjectAssetService(session, seeded.actor).declare_slot(
        seeded.project_id,
        AssetSlotDeclaration(
            slot_key=target_slot_key,
            lesson_unit_id=lesson.lesson_id,
            asset_type="video",
            cardinality=AssetCardinality.ONE,
            target_contract=AssetTargetContract(
                allowed_mime_types=("video/mp4",),
                require_clean_scan=True,
            ),
        ),
        request_id=f"video-seed-output-slot-{lesson_index}",
    )
    package = CreationPackage(
        id=new_uuid7(),
        organization_id=seeded.actor.organization_id,
        package_key=f"video.golden:{node.id}:{lesson.intro_selection_id}",
        source_project_id=seeded.project_id,
        source_workflow_run_id=run.id,
        source_node_run_id=node.id,
        source_artifact_version_id=lesson.intro_artifact_version_id,
        lesson_unit_id=lesson.lesson_id,
        context_snapshot_id=source_version.context_snapshot_id,
        source_prompt_snapshot_id=source_version.prompt_snapshot_id,
        package_type="video",
        status="ready",
        target_rules_json={
            "replace_modes": ["reject_if_occupied", "replace_active"],
            "allow_download": True,
        },
        content_hash=canonical_content_hash(
            {
                "intro_selection_id": str(lesson.intro_selection_id),
                "keyframe_file_version_id": str(lesson.keyframe_file_version_id),
            }
        ),
        created_at=now,
        created_by=seeded.actor.principal_id,
    )
    session.add(package)
    session.flush()
    package_item = CreationPackageItem(
        id=new_uuid7(),
        creation_package_id=package.id,
        item_key="video.intro.candidate",
        position=1,
        title="Classroom intro clip",
        business_prompt="Create one six-second classroom intro clip.",
        prompt_json={"style": "style.primary_math.paper_clay"},
        reference_asset_version_ids=[str(lesson.keyframe_file_version_id)],
        reference_assets_json=[
            {
                "asset_version_id": str(lesson.keyframe_file_version_id),
                "role": "shot_keyframe",
            }
        ],
        output_spec_json={"mime_type": "video/mp4", "duration_seconds": 6},
        target_slot_key=target_slot_key,
        consistency_key="style.primary_math.paper_clay",
        content_hash="2" * 64,
    )
    batch = CreationBatch(
        id=new_uuid7(),
        organization_id=seeded.actor.organization_id,
        owner_user_id=seeded.actor.user_id,
        source_kind="project",
        creation_package_id=package.id,
        source_project_id=seeded.project_id,
        source_workflow_run_id=run.id,
        source_node_run_id=node.id,
        studio_type="video",
        title="Classroom intro clip",
        status="completed",
        created_by=seeded.actor.principal_id,
        updated_by=seeded.actor.principal_id,
    )
    session.add_all([package_item, batch])
    session.flush()
    item = CreationItem(
        id=new_uuid7(),
        organization_id=seeded.actor.organization_id,
        creation_batch_id=batch.id,
        creation_package_item_id=package_item.id,
        item_key=package_item.item_key,
        title=package_item.title,
        status="review_required",
        target_slot_key=target_slot_key,
        created_by=seeded.actor.principal_id,
        updated_by=seeded.actor.principal_id,
    )
    session.add(item)
    session.flush()
    prompt = CreationPromptVersion(
        id=new_uuid7(),
        organization_id=seeded.actor.organization_id,
        creation_item_id=item.id,
        version_no=1,
        business_prompt=package_item.business_prompt,
        reference_asset_version_ids=[str(lesson.keyframe_file_version_id)],
        output_spec_json=package_item.output_spec_json,
        generation_profile="quality",
        content_hash="3" * 64,
        created_at=now,
        created_by=seeded.actor.principal_id,
    )
    session.add(prompt)
    session.flush()
    item.current_prompt_version_id = prompt.id
    job = GenerationJob(
        id=new_uuid7(),
        organization_id=seeded.actor.organization_id,
        project_id=seeded.project_id,
        node_run_id=node.id,
        lesson_unit_id=lesson.lesson_id,
        workflow_node_key="video.shots.generate",
        creation_prompt_version_id=prompt.id,
        creation_request_json={
            "intro_selection_id": str(lesson.intro_selection_id),
            "keyframe_file_version_id": str(lesson.keyframe_file_version_id),
        },
        job_type="video.golden_slice",
        status="succeeded",
        progress_percent=100,
        progress_message="Video generation completed",
        idempotency_key=f"video-seed-job-{lesson_index}",
        request_hash="4" * 64,
        priority=100,
        attempt_count=1,
        started_at=now,
        finished_at=now,
        created_by=seeded.actor.principal_id,
        updated_by=seeded.actor.principal_id,
    )
    video_asset = FileAsset(
        id=new_uuid7(),
        organization_id=seeded.actor.organization_id,
        asset_key=f"video.golden:{node.id}",
        asset_kind="video",
        status="active",
        retention_class="project_asset",
        created_by=seeded.actor.principal_id,
        updated_by=seeded.actor.principal_id,
    )
    session.add_all([job, video_asset])
    session.flush()
    video_version = FileAssetVersion(
        id=new_uuid7(),
        organization_id=seeded.actor.organization_id,
        file_asset_id=video_asset.id,
        version_no=1,
        storage_bucket="shanhaiedu",
        storage_key=f"immutable/{video_asset.id}/candidate.mp4",
        mime_type=mime_type,
        byte_size=4096,
        sha256="5" * 64,
        etag=f"etag-{video_asset.id}",
        width=1280,
        height=720,
        duration_ms=6000,
        scan_status="clean",
        metadata_json={"runtime": "video.golden_slice"},
        derived_from_version_id=lesson.keyframe_file_version_id,
        created_at=now,
        created_by=seeded.actor.principal_id,
    )
    session.add(video_version)
    session.flush()
    video_asset.current_version_id = video_version.id
    result = GenerationResult(
        id=new_uuid7(),
        organization_id=seeded.actor.organization_id,
        creation_item_id=item.id,
        generation_job_id=job.id,
        candidate_no=1,
        status="available",
        file_asset_version_id=video_version.id,
        output_json={
            "mime_type": "video/mp4",
            "byte_size": 4096,
            "sha256": video_version.sha256,
            "duration_ms": 6000,
        },
        created_at=now,
    )
    session.add(result)
    session.flush()
    return CompletedVideoCandidate(result.id, video_version.id, target_slot_key)
