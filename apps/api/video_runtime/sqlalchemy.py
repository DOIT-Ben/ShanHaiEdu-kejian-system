"""PostgreSQL transaction adapter for the golden classroom-intro video slice."""

from __future__ import annotations

import re
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.assets.provider_media import (
    ProviderMediaAssetVersion,
    SqlAlchemyProviderMediaAssetReader,
)
from apps.api.content_runtime.models import ContentRelease
from apps.api.content_runtime.runtime_port import SqlAlchemyRuntimeDefinitionReader
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.intro_selections.schemas import IntroSelectionRead
from apps.api.intro_selections.service import IntroSelectionService
from apps.api.model_gateway.contracts import MediaReference, ModelAuditContext, VideoGatewayResult
from apps.api.prompt_runtime.models import PromptSnapshot
from apps.api.prompt_runtime.service import PromptSnapshotService
from apps.api.runtime_boundary.ports import WorkflowExecutionContext
from apps.api.workflows.execution_port import SqlAlchemyWorkflowExecutionPort
from apps.api.workflows.models import NodeRun
from workflow.node_state import NodeStatus

from .contracts import (
    PreparedVideoRuntime,
    ValidatedVideoFile,
    VideoRuntimeError,
    VideoRuntimeResult,
    VideoRuntimeTransaction,
)
from .prompt import compile_video_prompt
from .store import RuntimeRows, SqlAlchemyVideoRuntimeStore
from .validator import require_validated_gateway_file

_RELEASE_KEY = "shanhai.primary_math.courseware@1.5.0"
_CAPABILITY = "video.image_to_video.6s_30s"


class SqlAlchemyVideoRuntimeTransactionFactory:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        actor: ActorContext,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._actor = actor
        self._fault_injector = fault_injector or _ignore_fault

    @contextmanager
    def begin(self) -> Generator[VideoRuntimeTransaction]:
        session = self._session_factory()
        try:
            with session.begin():
                yield SqlAlchemyVideoRuntimeTransaction(
                    session,
                    self._actor,
                    fault_injector=self._fault_injector,
                )
        finally:
            session.close()


class SqlAlchemyVideoRuntimeTransaction:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        fault_injector: Callable[[str], None],
    ) -> None:
        self._session = session
        self._actor = actor
        self._workflow = SqlAlchemyWorkflowExecutionPort(session, actor)
        self._definitions = SqlAlchemyRuntimeDefinitionReader(session, actor, self._workflow)
        self._media = SqlAlchemyProviderMediaAssetReader(session)
        self._store = SqlAlchemyVideoRuntimeStore(session, actor)
        self._fault_injector = fault_injector

    def prepare_start(
        self,
        node_run_id: UUID,
        keyframe_file_version_id: UUID,
        request_id: str,
    ) -> PreparedVideoRuntime | VideoRuntimeResult:
        execution = self._require_execution(node_run_id, for_update=True)
        existing = self._store.rows(node_run_id, for_update=True)
        if existing is not None:
            self._require_start_replay(existing, keyframe_file_version_id, request_id)
            return self._result(existing)

        selection = self._current_selection(execution)
        keyframe = self._keyframe(keyframe_file_version_id, execution.organization_id)
        materials = self._definitions.resolve_materials(node_run_id)
        self._require_release(
            materials.definition.content_release_id, materials.definition.node_binding
        )
        compiled = compile_video_prompt(materials, selection)
        snapshots = PromptSnapshotService(self._session, self._actor).freeze(
            node_run_id,
            context=compiled.context,
            prompt=compiled.prompt,
        )
        slot_key = _slot_key(execution.lesson_key)
        self._store.declare_slot(execution, slot_key, request_id)
        package_id = self._store.publish_package(
            execution,
            selection,
            keyframe,
            snapshots.context.id,
            snapshots.prompt.id,
            compiled.prompt,
            slot_key,
            request_id,
        )
        rows = self._store.create_generation(
            execution,
            package_id,
            keyframe,
            selection,
            compiled.prompt.compiled_prompt,
            request_id,
        )
        self._workflow.freeze_execution(
            execution,
            request_id=request_id,
            snapshot={
                "intro_selection_id": str(selection.id),
                "intro_artifact_version_id": str(selection.artifact_version_id),
                "intro_snapshot_hash": canonical_content_hash(selection.snapshot),
                "keyframe_file_version_id": str(keyframe.id),
                "keyframe_sha256": keyframe.sha256,
                "target_slot_key": slot_key,
            },
        )
        self._require_frozen_sources(rows, execution)
        self._workflow.start(node_run_id)
        return self._prepared(rows, execution)

    def prepare_poll(
        self,
        node_run_id: UUID,
        request_id: str,
    ) -> PreparedVideoRuntime | VideoRuntimeResult:
        del request_id
        execution = self._require_execution(node_run_id, for_update=True)
        rows = self._store.require_rows(node_run_id, for_update=True)
        if rows.job.status != "running":
            return self._result(rows)
        self._require_frozen_sources(rows, execution)
        return self._prepared(rows, execution)

    def record_pending(
        self,
        prepared: PreparedVideoRuntime,
        gateway_result: VideoGatewayResult,
    ) -> VideoRuntimeResult:
        rows = self._store.require_rows(prepared.node_run_id, for_update=True)
        private = self._store.private(rows.job)
        private["provider_task_id"] = gateway_result.provider_task_id
        private["provider_state"] = gateway_result.status.value
        self._store.set_private(rows.job, private)
        rows.job.status = "running"
        rows.job.progress_percent = 20 if gateway_result.status.value == "submitted" else 60
        rows.job.progress_message = (
            "Video generation submitted"
            if gateway_result.status.value == "submitted"
            else "Video generation processing"
        )
        self._store.touch(rows.job)
        rows.item.status = "generating"
        rows.batch.status = "running"
        return VideoRuntimeResult(
            node_run_id=prepared.node_run_id,
            generation_job_id=rows.job.id,
            status="submitted" if gateway_result.status.value == "submitted" else "processing",
            generation_result_id=None,
            file_asset_version_id=None,
        )

    def complete(
        self,
        prepared: PreparedVideoRuntime,
        gateway_result: VideoGatewayResult,
        validated_file: ValidatedVideoFile,
    ) -> VideoRuntimeResult:
        rows = self._store.require_rows(prepared.node_run_id, for_update=True)
        execution = self._require_execution(prepared.node_run_id, for_update=True)
        existing = self._store.generation_result(rows.job.id)
        if existing is not None:
            return self._result(rows)
        self._require_frozen_sources(rows, execution)
        require_validated_gateway_file(gateway_result, validated_file)
        result, version = self._store.create_candidate(
            rows,
            prepared,
            execution,
            validated_file,
            self._fault_injector,
        )
        rows.job.status = "succeeded"
        rows.job.progress_percent = 100
        rows.job.progress_message = "Video candidate ready for review"
        rows.job.error_code = None
        rows.job.finished_at = utc_now()
        self._store.touch(rows.job)
        rows.item.status = "review_required"
        rows.batch.status = "completed"
        self._workflow.transition(prepared.node_run_id, NodeStatus.REVIEW_REQUIRED)
        node = self._session.get(NodeRun, prepared.node_run_id)
        assert node is not None
        node.finished_at = utc_now()
        node.last_error_code = None
        return VideoRuntimeResult(
            node_run_id=prepared.node_run_id,
            generation_job_id=rows.job.id,
            status="completed",
            generation_result_id=result.id,
            file_asset_version_id=version.id,
        )

    def terminalize_failure(self, prepared: PreparedVideoRuntime, *, code: str) -> None:
        rows = self._store.rows(prepared.node_run_id, for_update=True)
        if rows is None or rows.job.status == "succeeded":
            return
        rows.job.status = "failed"
        rows.job.error_code = code[:100]
        rows.job.progress_message = "Video generation failed"
        rows.job.finished_at = utc_now()
        self._store.touch(rows.job)
        rows.item.status = "failed"
        rows.batch.status = "partially_completed"
        self._workflow.terminalize(prepared.node_run_id, code=code, cancelled=False)

    def _require_execution(
        self, node_run_id: UUID, *, for_update: bool
    ) -> WorkflowExecutionContext:
        try:
            execution = self._workflow.require_context(node_run_id, for_update=for_update)
        except Exception as exc:
            raise VideoRuntimeError(
                getattr(exc, "code", "VIDEO_RUNTIME_NODE_INVALID"),
                "the video node is not executable",
            ) from exc
        if (
            execution.node_key != "video.shots.generate"
            or execution.branch_key != "video"
            or execution.lesson_unit_id is None
            or execution.lesson_key is None
        ):
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_NODE_INVALID", "the node is not the video MVP node"
            )
        return execution

    def _require_release(self, release_id: UUID, binding: Mapping[str, object]) -> None:
        release = self._session.get(ContentRelease, release_id)
        if (
            release is None
            or release.status != "published"
            or release.release_key != _RELEASE_KEY
            or binding.get("model_capability") != _CAPABILITY
            or (binding.get("dependencies") != () and binding.get("dependencies") != [])
            or binding.get("entrypoint") is not True
        ):
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_RELEASE_INVALID",
                "the project is not bound to the 1.5.0 video golden release",
            )

    def _current_selection(self, execution: WorkflowExecutionContext) -> IntroSelectionRead:
        try:
            return IntroSelectionService(self._session, self._actor).current_consumable(
                project_id=execution.project_id,
                lesson_unit_id=cast(UUID, execution.lesson_unit_id),
            )
        except ApiError as exc:
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_INTRO_SELECTION_INVALID",
                "an exact consumable Intro selection is required",
            ) from exc

    def _keyframe(self, version_id: UUID, organization_id: UUID) -> ProviderMediaAssetVersion:
        value = self._media.get_clean_image_version(
            organization_id=organization_id,
            file_version_id=version_id,
        )
        if value is None or not value.mime_type.startswith("image/"):
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_KEYFRAME_INVALID",
                "one active clean image version is required",
            )
        return value

    def _require_frozen_sources(
        self,
        rows: RuntimeRows,
        execution: WorkflowExecutionContext,
    ) -> None:
        private = self._store.private(rows.job)
        selection = self._current_selection(execution)
        keyframe_id = _uuid(private.get("keyframe_file_version_id"))
        keyframe = self._keyframe(keyframe_id, execution.organization_id)
        if (
            str(selection.id) != private.get("intro_selection_id")
            or str(selection.artifact_version_id) != private.get("intro_artifact_version_id")
            or canonical_content_hash(selection.snapshot) != private.get("intro_snapshot_hash")
            or keyframe.sha256 != private.get("keyframe_sha256")
            or keyframe.mime_type != private.get("keyframe_mime_type")
        ):
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_FROZEN_SOURCE_CHANGED",
                "the selected Intro or keyframe is no longer consumable",
            )

    def _prepared(
        self,
        rows: RuntimeRows,
        execution: WorkflowExecutionContext,
    ) -> PreparedVideoRuntime:
        private = self._store.private(rows.job)
        snapshot = self._session.get(PromptSnapshot, rows.package.source_prompt_snapshot_id)
        if snapshot is None:
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_STATE_INVALID", "video prompt snapshot is missing"
            )
        return PreparedVideoRuntime(
            node_run_id=execution.node_run_id,
            generation_job_id=rows.job.id,
            organization_id=execution.organization_id,
            project_id=execution.project_id,
            lesson_unit_id=cast(UUID, execution.lesson_unit_id),
            creation_item_id=rows.item.id,
            audit_context=ModelAuditContext(
                organization_id=execution.organization_id,
                user_id=self._actor.user_id,
                project_id=execution.project_id,
                node_run_id=execution.node_run_id,
                generation_job_id=rows.job.id,
            ),
            prompt=snapshot.compiled_prompt,
            keyframe=MediaReference(
                file_version_id=_uuid(private.get("keyframe_file_version_id")),
                mime_type=cast(str, private.get("keyframe_mime_type")),
            ),
            duration_seconds=6,
            provider_task_id=cast(str | None, private.get("provider_task_id")),
        )

    def _result(self, rows: RuntimeRows) -> VideoRuntimeResult:
        if rows.job.status == "failed":
            raise VideoRuntimeError(
                rows.job.error_code or "VIDEO_RUNTIME_PROVIDER_FAILED",
                "video generation is terminally failed",
            )
        result = self._store.generation_result(rows.job.id)
        if rows.job.status == "succeeded":
            if result is None or result.file_asset_version_id is None:
                raise VideoRuntimeError("VIDEO_RUNTIME_STATE_INVALID", "video candidate is missing")
            return VideoRuntimeResult(
                node_run_id=rows.package.source_node_run_id,
                generation_job_id=rows.job.id,
                status="completed",
                generation_result_id=result.id,
                file_asset_version_id=result.file_asset_version_id,
            )
        private = self._store.private(rows.job)
        return VideoRuntimeResult(
            node_run_id=rows.package.source_node_run_id,
            generation_job_id=rows.job.id,
            status="processing" if private.get("provider_state") == "polling" else "submitted",
            generation_result_id=None,
            file_asset_version_id=None,
        )

    def _require_start_replay(
        self,
        rows: RuntimeRows,
        keyframe_id: UUID,
        request_id: str,
    ) -> None:
        private = self._store.private(rows.job)
        if private.get("start_request_id") != request_id or private.get(
            "keyframe_file_version_id"
        ) != str(keyframe_id):
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_REQUEST_CONFLICT",
                "the node is already bound to another video request",
            )


def _slot_key(lesson_key: str | None) -> str:
    if lesson_key is None:
        raise VideoRuntimeError("VIDEO_RUNTIME_NODE_INVALID", "video lesson key is missing")
    slug = re.sub(r"[^a-z0-9]+", "-", lesson_key.lower()).strip("-")
    if not slug:
        raise VideoRuntimeError("VIDEO_RUNTIME_NODE_INVALID", "video lesson key is invalid")
    return f"lesson.{slug}.video.intro"


def _uuid(value: object) -> UUID:
    try:
        return UUID(cast(str, value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise VideoRuntimeError(
            "VIDEO_RUNTIME_STATE_INVALID", "video UUID state is invalid"
        ) from exc


def _ignore_fault(_stage: str) -> None:
    return None
