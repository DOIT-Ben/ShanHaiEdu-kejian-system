"""Persistence helpers for the golden video runtime transaction."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
)
from apps.api.assets.project_service import ProjectAssetService
from apps.api.assets.provider_media import ProviderMediaAssetVersion
from apps.api.creation.execution_port import SqlAlchemyCreationPackagePort
from apps.api.creation.models import (
    CreationBatch,
    CreationItem,
    CreationPackage,
    CreationPromptVersion,
    GenerationResult,
)
from apps.api.creation.schemas import (
    GenerateCreationItemRequest,
    ProjectCreateCreationBatchRequest,
    SavePromptVersionRequest,
)
from apps.api.creation.service import CreationService
from apps.api.database import utc_now
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.intro_selections.schemas import IntroSelectionRead
from apps.api.jobs.models import GenerationJob
from apps.api.runtime_boundary.ports import (
    CreationPackageItemSpec,
    CreationPackageReferenceAssetSpec,
    CreationPackageSpec,
    WorkflowExecutionContext,
)
from workflow.prompt_runtime import CompiledPrompt

from .contracts import PreparedVideoRuntime, ValidatedVideoFile, VideoRuntimeError

PRIVATE_STATE_KEY = "video_runtime"


@dataclass(frozen=True, slots=True)
class RuntimeRows:
    package: CreationPackage
    batch: CreationBatch
    item: CreationItem
    prompt: CreationPromptVersion
    job: GenerationJob


class SqlAlchemyVideoRuntimeStore:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def declare_slot(
        self,
        execution: WorkflowExecutionContext,
        slot_key: str,
        request_id: str,
    ) -> None:
        ProjectAssetService(self._session, self._actor).declare_slot(
            execution.project_id,
            AssetSlotDeclaration(
                slot_key=slot_key,
                lesson_unit_id=execution.lesson_unit_id,
                asset_type="video",
                cardinality=AssetCardinality.ONE,
                required=False,
                target_contract=AssetTargetContract(
                    allowed_mime_types=("video/mp4",),
                    require_clean_scan=True,
                ),
            ),
            request_id=request_id,
        )

    def publish_package(
        self,
        execution: WorkflowExecutionContext,
        selection: IntroSelectionRead,
        keyframe: ProviderMediaAssetVersion,
        context_snapshot_id: UUID,
        prompt_snapshot_id: UUID,
        prompt: CompiledPrompt,
        slot_key: str,
        request_id: str,
    ) -> UUID:
        result = SqlAlchemyCreationPackagePort(self._session, self._actor).publish(
            CreationPackageSpec(
                project_id=execution.project_id,
                workflow_run_id=execution.workflow_run_id,
                node_run_id=execution.node_run_id,
                lesson_unit_id=execution.lesson_unit_id,
                artifact_version_id=selection.artifact_version_id,
                context_snapshot_id=context_snapshot_id,
                prompt_snapshot_id=prompt_snapshot_id,
                package_key=(
                    f"video.shots.generate:{execution.node_run_id}:{selection.artifact_version_id}"
                ),
                package_type="video",
                items=(
                    CreationPackageItemSpec(
                        item_key="video.intro.candidate",
                        position=1,
                        title="课堂导入短片",
                        business_prompt=prompt.editable_prompt,
                        prompt={
                            "template_refs": prompt.template_refs,
                            "layers": list(prompt.layers),
                            "content_hash": prompt.content_hash,
                        },
                        reference_assets=(
                            CreationPackageReferenceAssetSpec(
                                asset_version_id=keyframe.id,
                                role="shot_keyframe",
                            ),
                        ),
                        output_spec={"mime_type": "video/mp4", "duration_seconds": 6},
                        target_slot_key=slot_key,
                        consistency_key="style.primary_math.paper_clay",
                    ),
                ),
                target_rules={
                    "replace_modes": ["reject_if_occupied", "replace_active"],
                    "allow_download": True,
                },
                request_id=request_id,
            )
        )
        return result.creation_package_id

    def create_generation(
        self,
        execution: WorkflowExecutionContext,
        package_id: UUID,
        keyframe: ProviderMediaAssetVersion,
        selection: IntroSelectionRead,
        compiled_prompt: str,
        request_id: str,
    ) -> RuntimeRows:
        service = CreationService(self._session, self._actor, idempotency_ttl_seconds=3600)
        token = hashlib.sha256(f"{execution.node_run_id}:{request_id}".encode()).hexdigest()[:32]
        batch_read = service.create_batch(
            ProjectCreateCreationBatchRequest(
                source_kind="project",
                studio_type="video",
                title="课堂导入短片",
                creation_package_id=package_id,
            ),
            idempotency_key=f"video-runtime-batch-{token}",
            request_id=request_id,
        )
        item_read = batch_read.items[0]
        prompt_read = service.save_prompt_version(
            item_read.id,
            SavePromptVersionRequest(
                business_prompt=compiled_prompt,
                reference_asset_version_ids=[keyframe.id],
                output_spec={"mime_type": "video/mp4", "duration_seconds": 6},
                generation_profile="quality",
            ),
            idempotency_key=f"video-runtime-prompt-{token}",
            request_id=request_id,
        )
        accepted = service.generate_item(
            item_read.id,
            GenerateCreationItemRequest(prompt_version_id=prompt_read.id, candidate_count=1),
            idempotency_key=f"video-runtime-job-{token}",
            request_id=request_id,
        )
        rows = self.require_rows(execution.node_run_id, for_update=True)
        if rows.job.id != accepted.job_id:
            raise VideoRuntimeError("VIDEO_RUNTIME_STATE_INVALID", "video job binding is invalid")
        rows.job.status = "running"
        rows.job.started_at = utc_now()
        rows.job.progress_percent = 10
        rows.job.progress_message = "Preparing video generation"
        rows.item.status = "generating"
        rows.batch.status = "running"
        private = self.private(rows.job)
        private.update(
            {
                "start_request_id": request_id,
                "intro_selection_id": str(selection.id),
                "intro_artifact_version_id": str(selection.artifact_version_id),
                "intro_snapshot_hash": canonical_content_hash(selection.snapshot),
                "keyframe_file_version_id": str(keyframe.id),
                "keyframe_mime_type": keyframe.mime_type,
                "keyframe_sha256": keyframe.sha256,
                "provider_task_id": None,
                "provider_state": None,
            }
        )
        self.set_private(rows.job, private)
        self.touch(rows.job)
        return rows

    def create_candidate(
        self,
        rows: RuntimeRows,
        prepared: PreparedVideoRuntime,
        execution: WorkflowExecutionContext,
        validated: ValidatedVideoFile,
        fault_injector: Callable[[str], None],
    ) -> tuple[GenerationResult, FileAssetVersion]:
        asset = FileAsset(
            id=new_uuid7(),
            organization_id=execution.organization_id,
            asset_key=f"video-runtime:{prepared.node_run_id}",
            asset_kind="video",
            current_version_id=None,
            status="active",
            retention_class="project_asset",
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(asset)
        self._session.flush()
        version = FileAssetVersion(
            id=new_uuid7(),
            organization_id=execution.organization_id,
            file_asset_id=asset.id,
            version_no=1,
            storage_bucket=validated.storage_bucket,
            storage_key=validated.storage_key,
            mime_type=validated.mime_type,
            byte_size=validated.size_bytes,
            sha256=validated.sha256,
            etag=validated.etag,
            width=validated.width,
            height=validated.height,
            duration_ms=validated.duration_ms,
            page_count=None,
            scan_status="clean",
            metadata_json={"runtime": "video.shots.generate"},
            derived_from_version_id=prepared.keyframe.file_version_id,
            created_at=utc_now(),
            created_by=self._actor.principal_id,
        )
        self._session.add(version)
        self._session.flush()
        asset.current_version_id = version.id
        fault_injector("after_file_asset_version")
        result = GenerationResult(
            id=new_uuid7(),
            organization_id=execution.organization_id,
            creation_item_id=rows.item.id,
            generation_job_id=rows.job.id,
            candidate_no=1,
            status="available",
            file_asset_version_id=version.id,
            output_json={
                "mime_type": version.mime_type,
                "size_bytes": version.byte_size,
                "sha256": version.sha256,
                "width": version.width,
                "height": version.height,
                "duration_ms": version.duration_ms,
            },
            created_at=utc_now(),
        )
        self._session.add(result)
        self._session.flush()
        fault_injector("after_generation_result")
        return result, version

    def rows(self, node_run_id: UUID, *, for_update: bool) -> RuntimeRows | None:
        statement = select(CreationPackage).where(
            CreationPackage.organization_id == self._actor.organization_id,
            CreationPackage.source_node_run_id == node_run_id,
        )
        if for_update:
            statement = statement.with_for_update()
        package = self._session.scalar(statement)
        if package is None:
            return None
        batch = self._session.scalar(
            select(CreationBatch).where(CreationBatch.creation_package_id == package.id)
        )
        if batch is None:
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_STATE_INVALID", "video creation batch is missing"
            )
        item = self._session.scalar(
            select(CreationItem).where(CreationItem.creation_batch_id == batch.id)
        )
        if item is None or item.current_prompt_version_id is None:
            raise VideoRuntimeError("VIDEO_RUNTIME_STATE_INVALID", "video creation item is missing")
        prompt = self._session.get(CreationPromptVersion, item.current_prompt_version_id)
        job = self._session.scalar(
            select(GenerationJob).where(
                GenerationJob.creation_prompt_version_id == item.current_prompt_version_id
            )
        )
        if prompt is None or job is None:
            raise VideoRuntimeError(
                "VIDEO_RUNTIME_STATE_INVALID", "video generation job is missing"
            )
        return RuntimeRows(package=package, batch=batch, item=item, prompt=prompt, job=job)

    def require_rows(self, node_run_id: UUID, *, for_update: bool) -> RuntimeRows:
        rows = self.rows(node_run_id, for_update=for_update)
        if rows is None:
            raise VideoRuntimeError("VIDEO_RUNTIME_NOT_STARTED", "video generation has not started")
        return rows

    def generation_result(self, job_id: UUID) -> GenerationResult | None:
        return self._session.scalar(
            select(GenerationResult).where(
                GenerationResult.generation_job_id == job_id,
                GenerationResult.candidate_no == 1,
            )
        )

    @staticmethod
    def private(job: GenerationJob) -> dict[str, Any]:
        payload = job.creation_request_json or {}
        value = payload.get(PRIVATE_STATE_KEY)
        if not isinstance(value, Mapping):
            return {}
        return dict(cast(Mapping[str, Any], value))

    @staticmethod
    def set_private(job: GenerationJob, private: dict[str, Any]) -> None:
        payload = dict(job.creation_request_json or {})
        payload[PRIVATE_STATE_KEY] = private
        job.creation_request_json = payload

    def touch(self, job: GenerationJob) -> None:
        job.updated_by = self._actor.principal_id
        job.lock_version += 1
