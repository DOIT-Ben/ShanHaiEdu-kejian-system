from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.assets.video_port import VideoFileVersion, VideoKeyframe
from apps.api.creation.schemas import (
    AdoptGenerationResultRequest,
    AdoptionRead,
    ProjectSourceSaveRequest,
    SaveToProjectOperationRead,
)
from apps.api.creation.service import CreationService
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.intro_selections.schemas import IntroSelectionRead
from apps.api.intro_selections.service import IntroSelectionService
from apps.api.jobs.schemas import AcceptedJobData
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.video_golden_slice.package_builder import VideoGoldenSlicePackageBuilder
from apps.api.video_golden_slice.repository import (
    VideoGoldenSliceRepository,
    VideoResultContext,
)
from apps.api.video_golden_slice.schemas import (
    SaveVideoAdoptionRequest,
    StartVideoGenerationRequest,
    VideoGoldenSlice,
    VideoGoldenSliceCandidate,
)


class VideoGoldenSliceService:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        idempotency_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._actor = actor
        self._repository = VideoGoldenSliceRepository(session, actor)
        self._idempotency_ttl_seconds = idempotency_ttl_seconds

    def start(
        self,
        project_id: UUID,
        lesson_id: UUID,
        payload: StartVideoGenerationRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> AcceptedJobData:
        request_payload = payload.model_dump(mode="json")

        def authorize() -> object:
            return ProjectAccessService(self._session, self._actor).require(
                project_id,
                ProjectAction.GENERATE,
                for_update=True,
            )

        def command() -> CommandResult:
            return self._start_command(
                project_id,
                lesson_id,
                payload,
                idempotency_key=idempotency_key,
                request_id=request_id,
            )

        result = IdempotencyService(
            self._session,
            self._actor.organization_id,
            ttl_seconds=self._idempotency_ttl_seconds,
        ).execute(
            scope=f"video-golden-slice.start:{project_id}:{lesson_id}",
            key=idempotency_key,
            payload=request_payload,
            authorize=authorize,
            command=command,
        )
        return AcceptedJobData.model_validate(result.body)

    def _start_command(
        self,
        project_id: UUID,
        lesson_id: UUID,
        payload: StartVideoGenerationRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> CommandResult:
        context = self._repository.lesson_context(project_id, lesson_id, for_update=True)
        if context is None:
            raise self._lesson_not_found()
        selection = IntroSelectionService(self._session, self._actor).current_consumable(
            project_id=project_id,
            lesson_unit_id=lesson_id,
        )
        keyframe, version_exists = self._repository.keyframe_context(
            project_id,
            lesson_id,
            payload.keyframe_file_asset_version_id,
            for_update=True,
        )
        if keyframe is None:
            raise _keyframe_error(version_exists)
        if self._repository.jobs.active_exists(project_id, lesson_id, for_update=True):
            raise ApiError(
                status_code=409,
                code="VIDEO_GENERATION_ALREADY_ACTIVE",
                message="This lesson already has an active video generation.",
            )
        accepted = VideoGoldenSlicePackageBuilder(self._session, self._actor).create(
            context,
            selection,
            keyframe,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )
        return CommandResult(
            status_code=202,
            body=accepted.model_dump(mode="json"),
            resource_type="generation_job",
            resource_id=accepted.job_id,
        )

    def get(self, project_id: UUID, lesson_id: UUID) -> VideoGoldenSlice:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.VIEW,
        )
        if self._repository.lesson_context(project_id, lesson_id) is None:
            raise self._lesson_not_found()
        selection = IntroSelectionService(self._session, self._actor).current_consumable(
            project_id=project_id,
            lesson_unit_id=lesson_id,
        )
        job = self._repository.latest_job(project_id, lesson_id)
        keyframe = self._repository.assets.current_keyframe(project_id, lesson_id)
        frozen = _frozen_inputs(
            job.creation_request if job is not None else None, selection, keyframe
        )
        result = self._repository.result_for_job(job.read.id) if job is not None else None
        candidate = self._candidate(project_id, lesson_id, result)
        return VideoGoldenSlice(
            project_id=project_id,
            lesson_unit_id=lesson_id,
            intro_selection_id=frozen[0],
            intro_artifact_version_id=frozen[1],
            keyframe_file_asset_version_id=frozen[2],
            keyframe_slot_key=frozen[3],
            job=job.read if job is not None else None,
            candidate=candidate,
        )

    def _candidate(
        self, project_id: UUID, lesson_id: UUID, result: VideoResultContext | None
    ) -> VideoGoldenSliceCandidate | None:
        if result is None:
            return None
        if not _is_verified_candidate(result):
            raise ApiError(
                status_code=409,
                code="VIDEO_GENERATION_STATE_INVALID",
                message="The video candidate lacks verified immutable file facts.",
            )
        version = result.file_version
        facts = result.result
        assert version.duration_ms is not None
        return VideoGoldenSliceCandidate(
            result_id=facts.result_id,
            file_asset_version_id=version.id,
            mime_type=version.mime_type,
            byte_size=version.byte_size,
            sha256=version.sha256,
            duration_ms=version.duration_ms,
            playback_url=_playback_url(project_id, lesson_id, facts.result_id),
            adoption_id=facts.active_adoption_id,
            saved_binding_id=self._repository.assets.saved_binding_id(facts.result_id),
        )

    def adopt(
        self,
        project_id: UUID,
        lesson_id: UUID,
        result_id: UUID,
        payload: AdoptGenerationResultRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> AdoptionRead:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.GENERATE,
        )
        context = self._repository.result_context(project_id, lesson_id, result_id)
        if context is None or not _is_verified_candidate(context):
            raise self._result_not_found()
        return self._creation().adopt_result(
            result_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request_id,
        )

    def save(
        self,
        project_id: UUID,
        lesson_id: UUID,
        adoption_id: UUID,
        payload: SaveVideoAdoptionRequest,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> SaveToProjectOperationRead:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.EDIT,
        )
        request_payload = payload.model_dump(mode="json")

        def authorize() -> object:
            return ProjectAccessService(self._session, self._actor).require(
                project_id,
                ProjectAction.EDIT,
                for_update=True,
            )

        def command() -> CommandResult:
            return self._save_command(
                project_id,
                lesson_id,
                adoption_id,
                idempotency_key=idempotency_key,
                request_id=request_id,
            )

        result = IdempotencyService(
            self._session,
            self._actor.organization_id,
            ttl_seconds=self._idempotency_ttl_seconds,
        ).execute(
            scope=f"video-golden-slice.save:{adoption_id}",
            key=idempotency_key,
            payload=request_payload,
            authorize=authorize,
            command=command,
        )
        return SaveToProjectOperationRead.model_validate(result.body)

    def _save_command(
        self,
        project_id: UUID,
        lesson_id: UUID,
        adoption_id: UUID,
        *,
        idempotency_key: str,
        request_id: str,
    ) -> CommandResult:
        context = self._repository.result_context_for_adoption(project_id, lesson_id, adoption_id)
        if context is None or not _is_verified_candidate(context):
            raise ApiError(
                status_code=404,
                code="VIDEO_ADOPTION_NOT_FOUND",
                message="The video adoption was not found.",
            )
        replace_mode = (
            "replace_active"
            if self._repository.assets.target_has_active_binding(
                project_id, context.result.target_slot_key
            )
            else "reject_if_occupied"
        )
        save_key = "video-save:" + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        saved = self._creation().save_adoption(
            adoption_id,
            ProjectSourceSaveRequest(source_kind="project", replace_mode=replace_mode),
            idempotency_key=save_key,
            request_id=request_id,
        )
        return CommandResult(
            status_code=200,
            body=saved.model_dump(mode="json"),
            resource_type="save_to_project_operation",
            resource_id=saved.operation_id,
        )

    def playback_file(
        self,
        project_id: UUID,
        lesson_id: UUID,
        result_id: UUID,
    ) -> VideoFileVersion:
        ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.VIEW,
        )
        context = self._repository.result_context(project_id, lesson_id, result_id)
        if context is None or not _is_verified_candidate(context):
            raise self._result_not_found()
        return context.file_version

    def _creation(self) -> CreationService:
        return CreationService(
            self._session,
            self._actor,
            idempotency_ttl_seconds=self._idempotency_ttl_seconds,
        )

    @staticmethod
    def _lesson_not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="VIDEO_LESSON_NOT_FOUND",
            message="The active video lesson was not found.",
        )

    @staticmethod
    def _result_not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="VIDEO_RESULT_NOT_FOUND",
            message="The video generation result was not found.",
        )


def _uuid_value(value: object, *, code: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ApiError(
            status_code=409,
            code=code,
            message="The frozen video generation state is invalid.",
        ) from exc


def _string_value(value: object, *, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise ApiError(
            status_code=409,
            code=code,
            message="The frozen video generation state is invalid.",
        )
    return value


def _playback_url(project_id: UUID, lesson_id: UUID, result_id: UUID) -> str:
    return f"/api/v2/projects/{project_id}/lessons/{lesson_id}/video/results/{result_id}/content"


def _keyframe_error(version_exists: bool) -> ApiError:
    return ApiError(
        status_code=409 if version_exists else 404,
        code="VIDEO_KEYFRAME_INVALID" if version_exists else "VIDEO_KEYFRAME_NOT_FOUND",
        message=(
            "The keyframe is not the active clean image for this lesson."
            if version_exists
            else "The keyframe file version was not found."
        ),
    )


def _is_verified_candidate(context: VideoResultContext) -> bool:
    version = context.file_version
    return bool(
        context.result.status == "available"
        and version.mime_type == "video/mp4"
        and version.scan_status == "clean"
        and version.byte_size > 0
        and version.duration_ms is not None
        and 5_500 <= version.duration_ms <= 6_500
    )


def _frozen_inputs(
    request: dict[str, object] | None,
    selection: IntroSelectionRead,
    keyframe: VideoKeyframe | None,
) -> tuple[UUID, UUID, UUID | None, str | None]:
    if request is None:
        return (
            selection.id,
            selection.artifact_version_id,
            None if keyframe is None else keyframe.version_id,
            None if keyframe is None else keyframe.slot_key,
        )
    code = "VIDEO_GENERATION_STATE_INVALID"
    return (
        _uuid_value(request.get("intro_selection_id"), code=code),
        _uuid_value(request.get("intro_artifact_version_id"), code=code),
        _uuid_value(request.get("keyframe_file_version_id"), code=code),
        _string_value(request.get("keyframe_slot_key"), code=code),
    )
