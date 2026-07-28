"""Video golden-slice facade over module-owned application ports."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.assets.video_port import VideoAssetPort, VideoFileVersion, VideoKeyframe
from apps.api.creation.video_port import VideoCreationPort, VideoResultFacts
from apps.api.identity.context import ActorContext
from apps.api.jobs.video_port import VideoJobPort, VideoJobProjection
from apps.api.lessons.video_scope_port import VideoLessonScope, VideoLessonScopeReader
from apps.api.workflows.video_scope_port import VideoWorkflowPort, VideoWorkflowScope


@dataclass(frozen=True, slots=True)
class VideoLessonContext:
    lesson: VideoLessonScope
    workflow: VideoWorkflowScope


@dataclass(frozen=True, slots=True)
class VideoResultContext:
    result: VideoResultFacts
    file_version: VideoFileVersion


class VideoGoldenSliceRepository:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self.lessons = VideoLessonScopeReader(session, actor)
        self.workflows = VideoWorkflowPort(session, actor)
        self.assets = VideoAssetPort(session, actor)
        self.creation = VideoCreationPort(session, actor)
        self.jobs = VideoJobPort(session, actor)

    def lesson_context(
        self, project_id: UUID, lesson_id: UUID, *, for_update: bool = False
    ) -> VideoLessonContext | None:
        lesson = self.lessons.active(project_id, lesson_id, for_update=for_update)
        workflow = self.workflows.active_scope(project_id, lesson_id, for_update=for_update)
        if lesson is None or workflow is None:
            return None
        return VideoLessonContext(lesson=lesson, workflow=workflow)

    def keyframe_context(
        self, project_id: UUID, lesson_id: UUID, version_id: UUID, *, for_update: bool = False
    ) -> tuple[VideoKeyframe | None, bool]:
        return self.assets.keyframe(project_id, lesson_id, version_id, for_update=for_update)

    def latest_job(self, project_id: UUID, lesson_id: UUID) -> VideoJobProjection | None:
        return self.jobs.latest(project_id, lesson_id)

    def result_context(
        self, project_id: UUID, lesson_id: UUID, result_id: UUID, *, for_update: bool = False
    ) -> VideoResultContext | None:
        result = self.creation.result(project_id, lesson_id, result_id, for_update=for_update)
        return self._with_file(result)

    def result_for_job(self, job_id: UUID) -> VideoResultContext | None:
        return self._with_file(self.creation.result_for_job(job_id))

    def result_context_for_adoption(
        self, project_id: UUID, lesson_id: UUID, adoption_id: UUID
    ) -> VideoResultContext | None:
        return self._with_file(
            self.creation.result_for_adoption(project_id, lesson_id, adoption_id)
        )

    def _with_file(self, result: VideoResultFacts | None) -> VideoResultContext | None:
        if result is None:
            return None
        version = self.assets.file_version(result.file_version_id)
        if version is None:
            return None
        return VideoResultContext(result=result, file_version=version)
