from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.video_source_port import VideoSourceArtifactReader
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
)
from apps.api.assets.project_service import ProjectAssetService
from apps.api.assets.video_port import VideoKeyframe
from apps.api.creation.video_port import VideoCreationInput, VideoCreationPort
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.intro_selections.schemas import IntroSelectionRead
from apps.api.jobs.schemas import AcceptedJobData
from apps.api.jobs.video_port import VideoJobInput, VideoJobPort
from apps.api.video_golden_slice.repository import VideoLessonContext


class VideoGoldenSlicePackageBuilder:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def create(
        self,
        context: VideoLessonContext,
        selection: IntroSelectionRead,
        keyframe: VideoKeyframe,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> AcceptedJobData:
        source = VideoSourceArtifactReader(self._session, self._actor.organization_id).get(
            selection.artifact_version_id
        )
        if (
            source is None
            or source.context_snapshot_id is None
            or source.prompt_snapshot_id is None
        ):
            raise ApiError(
                status_code=409,
                code="VIDEO_INTRO_SELECTION_INVALID",
                message="The exact Intro selection lacks immutable generation context.",
            )
        node_id = self._workflow_node(context)
        target_slot_key = self._declare_target(context, request_id=request_id)
        request_payload = _request_payload(selection, keyframe)
        routing = VideoCreationPort(self._session, self._actor).create(
            VideoCreationInput(
                project_id=context.lesson.project_id,
                lesson_id=context.lesson.lesson_unit_id,
                workflow_run_id=context.workflow.workflow_run_id,
                node_run_id=node_id,
                artifact_version_id=selection.artifact_version_id,
                context_snapshot_id=source.context_snapshot_id,
                prompt_snapshot_id=source.prompt_snapshot_id,
                selection_id=selection.id,
                selection_snapshot=selection.snapshot,
                business_prompt=_business_prompt(selection),
                keyframe_version_id=keyframe.version_id,
                target_slot_key=target_slot_key,
            ),
            now=utc_now(),
        )
        return VideoJobPort(self._session, self._actor).create(
            VideoJobInput(
                project_id=context.lesson.project_id,
                lesson_id=context.lesson.lesson_unit_id,
                node_run_id=node_id,
                prompt_version_id=routing.prompt_version_id,
                batch_id=routing.batch_id,
                request_payload=request_payload,
                idempotency_key=idempotency_key,
            ),
            request_id=request_id,
        )

    def _workflow_node(self, context: VideoLessonContext) -> UUID:
        from apps.api.workflows.video_scope_port import VideoWorkflowPort

        return VideoWorkflowPort(self._session, self._actor).create_queued_node(context.workflow)

    def _declare_target(self, context: VideoLessonContext, *, request_id: str) -> str:
        slot_key = f"lesson.{context.lesson.position:02d}.video.intro.selected"
        ProjectAssetService(self._session, self._actor).declare_slot(
            context.lesson.project_id,
            AssetSlotDeclaration(
                slot_key=slot_key,
                lesson_unit_id=context.lesson.lesson_unit_id,
                asset_type="video",
                cardinality=AssetCardinality.ONE,
                target_contract=AssetTargetContract(
                    allowed_mime_types=("video/mp4",),
                    require_clean_scan=True,
                ),
            ),
            request_id=request_id,
        )
        return slot_key


def _request_payload(selection: IntroSelectionRead, keyframe: VideoKeyframe) -> dict[str, object]:
    return {
        "intro_selection_id": str(selection.id),
        "intro_artifact_version_id": str(selection.artifact_version_id),
        "keyframe_file_version_id": str(keyframe.version_id),
        "keyframe_slot_key": keyframe.slot_key,
    }


def _business_prompt(selection: IntroSelectionRead) -> str:
    context = json.dumps(
        {
            "artifact_version_id": str(selection.artifact_version_id),
            "selection_id": str(selection.id),
            "snapshot": selection.snapshot,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    prompt = (
        "依据exact已采用课堂导入方案与唯一正式关键帧生成一个约6秒候选;"
        "保持关键帧主体、构图与纸艺黏土风格, 禁止字幕、旁白、水印、Logo和额外镜头."
        f"\n\n[intro_selection.snapshot]\n{context}"
    )
    if len(context.encode("utf-8")) > 100_000 or len(prompt) > 100_000:
        raise ApiError(
            status_code=409,
            code="VIDEO_INTRO_SELECTION_INVALID",
            message="The exact Intro selection exceeds the video prompt boundary.",
        )
    return prompt
