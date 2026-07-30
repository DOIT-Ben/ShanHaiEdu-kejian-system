from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.models import Approval, Artifact, ArtifactVersion
from apps.api.assets.models import FileAssetVersion
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
    ReplaceMode,
)
from apps.api.assets.project_service import ProjectAssetService
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.intro_selections.service import IntroSelectionService
from apps.api.lessons.models import LessonBranchConfig, LessonUnit
from apps.api.workflows.models import BranchRun, WorkflowRun
from tests.integration.intro_selection_support import prepare_approved_option_set
from tests.integration.test_project_asset_bindings import (
    seed_file_version,  # pyright: ignore[reportUnknownVariableType]
)


@dataclass(frozen=True, slots=True)
class VideoLessonFact:
    lesson_id: UUID
    lesson_key: str
    intro_artifact_version_id: UUID
    intro_selection_id: UUID
    keyframe_file_version_id: UUID
    keyframe_slot_key: str


@dataclass(frozen=True, slots=True)
class VideoProjectSeed:
    actor: ActorContext
    project_id: UUID
    lessons: tuple[VideoLessonFact, ...]


async def seed_video_project(
    factory: sessionmaker[Session],
    *,
    lesson_count: int = 2,
) -> VideoProjectSeed:
    if lesson_count not in {1, 2}:
        raise ValueError("video test seed supports one or two lessons")
    prepared = await prepare_approved_option_set(factory)
    with factory() as session, session.begin():
        first_selection = IntroSelectionService(session, prepared.actor).select_teacher(
            project_id=prepared.project_id,
            lesson_unit_id=prepared.lesson_unit_id,
            artifact_version_id=prepared.version_id,
            option_key=prepared.option_keys[0],
            reason="Use the exact approved Intro option for the video slice.",
            idempotency_key=f"video-seed-select-{prepared.lesson_unit_id}",
            ttl_seconds=3600,
        )
        first = session.get(LessonUnit, prepared.lesson_unit_id)
        assert first is not None
        _activate_video_branch(session, prepared.actor, prepared.project_id, first)
        first_keyframe, first_slot = _bind_keyframe(
            session,
            prepared.actor,
            prepared.project_id,
            first,
        )
        facts = [
            VideoLessonFact(
                lesson_id=first.id,
                lesson_key=first.lesson_key,
                intro_artifact_version_id=prepared.version_id,
                intro_selection_id=first_selection.id,
                keyframe_file_version_id=first_keyframe.id,
                keyframe_slot_key=first_slot,
            )
        ]
        if lesson_count == 2:
            second, second_version = _clone_second_lesson(
                session,
                prepared.actor,
                project_id=prepared.project_id,
                first_lesson=first,
                source_version_id=prepared.version_id,
            )
            second_selection = IntroSelectionService(session, prepared.actor).select_teacher(
                project_id=prepared.project_id,
                lesson_unit_id=second.id,
                artifact_version_id=second_version.id,
                option_key=prepared.option_keys[1],
                reason="Use the second lesson's exact approved Intro option.",
                idempotency_key=f"video-seed-select-{second.id}",
                ttl_seconds=3600,
            )
            second_keyframe, second_slot = _bind_keyframe(
                session,
                prepared.actor,
                prepared.project_id,
                second,
            )
            facts.append(
                VideoLessonFact(
                    lesson_id=second.id,
                    lesson_key=second.lesson_key,
                    intro_artifact_version_id=second_version.id,
                    intro_selection_id=second_selection.id,
                    keyframe_file_version_id=second_keyframe.id,
                    keyframe_slot_key=second_slot,
                )
            )
    return VideoProjectSeed(
        actor=prepared.actor,
        project_id=prepared.project_id,
        lessons=tuple(facts),
    )


def _activate_video_branch(
    session: Session,
    actor: ActorContext,
    project_id: UUID,
    lesson: LessonUnit,
) -> None:
    run = session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.project_id == project_id,
            WorkflowRun.status == "active",
        )
    )
    assert run is not None
    branch = session.scalar(
        select(BranchRun).where(
            BranchRun.workflow_run_id == run.id,
            BranchRun.lesson_unit_id == lesson.id,
            BranchRun.branch_key == "video",
        )
    )
    config = session.scalar(
        select(LessonBranchConfig).where(
            LessonBranchConfig.lesson_unit_id == lesson.id,
            LessonBranchConfig.branch_key == "video",
        )
    )
    assert branch is not None and config is not None
    branch.status = "active"
    branch.started_at = branch.started_at or utc_now()
    config.enabled = True
    branch.updated_by = actor.principal_id
    config.updated_by = actor.principal_id


def _bind_keyframe(
    session: Session,
    actor: ActorContext,
    project_id: UUID,
    lesson: LessonUnit,
) -> tuple[FileAssetVersion, str]:
    version = seed_file_version(session, actor)
    slot_key = f"lesson.{lesson.position:02d}.video.keyframe"
    service = ProjectAssetService(session, actor)
    slot = service.declare_slot(
        project_id,
        AssetSlotDeclaration(
            slot_key=slot_key,
            lesson_unit_id=lesson.id,
            asset_type="image",
            cardinality=AssetCardinality.ONE,
            required=True,
            target_contract=AssetTargetContract(
                allowed_mime_types=("image/png",),
                require_clean_scan=True,
            ),
        ),
        request_id=f"video-seed-keyframe-slot-{lesson.id}",
    )
    service.bind(
        slot.id,
        file_asset_version_id=version.id,
        source_artifact_version_id=None,
        replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
        position=None,
        request_id=f"video-seed-keyframe-bind-{lesson.id}",
    )
    return version, slot_key


def _clone_second_lesson(
    session: Session,
    actor: ActorContext,
    *,
    project_id: UUID,
    first_lesson: LessonUnit,
    source_version_id: UUID,
) -> tuple[LessonUnit, ArtifactVersion]:
    source_version = session.get(ArtifactVersion, source_version_id)
    source_artifact = session.get(Artifact, source_version.artifact_id if source_version else None)
    source_approval = session.scalar(
        select(Approval)
        .where(Approval.artifact_version_id == source_version_id, Approval.action == "approve")
        .order_by(Approval.created_at.desc(), Approval.id.desc())
    )
    run = session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.project_id == project_id,
            WorkflowRun.status == "active",
        )
    )
    assert source_version is not None and source_artifact is not None
    assert source_approval is not None and run is not None
    second = LessonUnit(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project_id,
        lesson_key="LESSON-002",
        position=2,
        title="Second lesson",
        scope_summary="Independent second-lesson scope",
        objective_summary="Independent second-lesson objective",
        estimated_minutes=first_lesson.estimated_minutes,
        source_division_version_id=first_lesson.source_division_version_id,
        status="active",
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(second)
    session.flush()
    config = LessonBranchConfig(
        id=new_uuid7(),
        lesson_unit_id=second.id,
        branch_key="video",
        enabled=True,
        settings_json={},
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    branch = BranchRun(
        id=new_uuid7(),
        workflow_run_id=run.id,
        lesson_unit_id=second.id,
        branch_key="video",
        status="active",
        started_at=utc_now(),
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    artifact = Artifact(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project_id,
        lesson_unit_id=second.id,
        branch_key="intro_options",
        artifact_key="intro-options:LESSON-002",
        artifact_type="intro_option_set",
        content_definition_version_id=source_artifact.content_definition_version_id,
        status="approved",
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add_all([config, branch, artifact])
    session.flush()
    content = deepcopy(source_version.content_json)
    content["lesson_unit_id"] = str(second.id)
    content["source_lesson_unit_key"] = second.lesson_key
    options = content.get("options")
    assert isinstance(options, list)
    for option in options:
        assert isinstance(option, dict)
        option["lesson_unit_key"] = second.lesson_key
    version = ArtifactVersion(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        artifact_id=artifact.id,
        version_no=1,
        content_json=content,
        content_hash=canonical_content_hash(content),
        render_summary_json=source_version.render_summary_json,
        source_kind="manual",
        source_node_run_id=source_version.source_node_run_id,
        context_snapshot_id=source_version.context_snapshot_id,
        prompt_snapshot_id=source_version.prompt_snapshot_id,
        validation_report_json=source_version.validation_report_json,
        created_by=actor.principal_id,
    )
    session.add(version)
    session.flush()
    artifact.current_submitted_version_id = version.id
    artifact.current_approved_version_id = version.id
    session.add(
        Approval(
            id=new_uuid7(),
            organization_id=actor.organization_id,
            artifact_version_id=version.id,
            action="approve",
            actor_type="user",
            actor_user_id=actor.user_id,
            comment="Approve the second lesson Intro fixture.",
            quality_evidence_json=source_approval.quality_evidence_json,
            policy_snapshot_json=source_approval.policy_snapshot_json,
            created_by=actor.principal_id,
        )
    )
    session.flush()
    return second, version
