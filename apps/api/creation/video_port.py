"""Creation-owned package, candidate, and adoption facts for video generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.creation.models import (
    Adoption,
    CreationBatch,
    CreationItem,
    CreationPackage,
    CreationPackageItem,
    CreationPromptVersion,
    GenerationResult,
)
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.reliability.idempotency import canonical_request_hash


@dataclass(frozen=True, slots=True)
class VideoCreationInput:
    project_id: UUID
    lesson_id: UUID
    workflow_run_id: UUID
    node_run_id: UUID
    artifact_version_id: UUID
    context_snapshot_id: UUID
    prompt_snapshot_id: UUID
    selection_id: UUID
    selection_snapshot: dict[str, object]
    business_prompt: str
    keyframe_version_id: UUID
    target_slot_key: str


@dataclass(frozen=True, slots=True)
class VideoCreationRouting:
    batch_id: UUID
    prompt_version_id: UUID


@dataclass(frozen=True, slots=True)
class VideoResultFacts:
    result_id: UUID
    generation_job_id: UUID
    file_version_id: UUID
    target_slot_key: str
    active_adoption_id: UUID | None
    status: str


class VideoCreationPort:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def create(self, data: VideoCreationInput, *, now: datetime) -> VideoCreationRouting:
        package = self._package(data, now=now)
        self._session.add(package)
        self._session.flush()
        package_item = self._package_item(package.id, data)
        batch = self._batch(package.id, data)
        self._session.add_all([package_item, batch])
        self._session.flush()
        item = self._item(batch.id, package_item)
        self._session.add(item)
        self._session.flush()
        prompt = self._prompt(item.id, package_item, data.keyframe_version_id, now=now)
        self._session.add(prompt)
        self._session.flush()
        item.current_prompt_version_id = prompt.id
        return VideoCreationRouting(batch_id=batch.id, prompt_version_id=prompt.id)

    def result(
        self, project_id: UUID, lesson_id: UUID, result_id: UUID, *, for_update: bool = False
    ) -> VideoResultFacts | None:
        statement = (
            select(GenerationResult, CreationItem)
            .join(CreationItem, CreationItem.id == GenerationResult.creation_item_id)
            .join(CreationBatch, CreationBatch.id == CreationItem.creation_batch_id)
            .join(CreationPackage, CreationPackage.id == CreationBatch.creation_package_id)
            .where(
                GenerationResult.id == result_id,
                GenerationResult.organization_id == self._actor.organization_id,
                CreationItem.organization_id == self._actor.organization_id,
                CreationBatch.organization_id == self._actor.organization_id,
                CreationBatch.source_project_id == project_id,
                CreationPackage.organization_id == self._actor.organization_id,
                CreationPackage.lesson_unit_id == lesson_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=(GenerationResult, CreationItem))
        row = self._session.execute(statement).one_or_none()
        return None if row is None else _result_fact(row[0], row[1])

    def result_for_job(self, job_id: UUID) -> VideoResultFacts | None:
        result_id = self._session.scalar(
            select(GenerationResult.id)
            .where(
                GenerationResult.organization_id == self._actor.organization_id,
                GenerationResult.generation_job_id == job_id,
                GenerationResult.status == "available",
            )
            .order_by(GenerationResult.candidate_no)
            .limit(1)
        )
        if result_id is None:
            return None
        row = self._session.execute(
            select(GenerationResult, CreationItem)
            .join(CreationItem, CreationItem.id == GenerationResult.creation_item_id)
            .where(GenerationResult.id == result_id)
        ).one()
        return _result_fact(row[0], row[1])

    def result_for_adoption(
        self, project_id: UUID, lesson_id: UUID, adoption_id: UUID
    ) -> VideoResultFacts | None:
        result_id = self._session.scalar(
            select(GenerationResult.id)
            .join(Adoption, Adoption.generation_result_id == GenerationResult.id)
            .join(CreationItem, CreationItem.id == GenerationResult.creation_item_id)
            .join(CreationBatch, CreationBatch.id == CreationItem.creation_batch_id)
            .join(CreationPackage, CreationPackage.id == CreationBatch.creation_package_id)
            .where(
                Adoption.id == adoption_id,
                Adoption.organization_id == self._actor.organization_id,
                CreationBatch.source_project_id == project_id,
                CreationPackage.lesson_unit_id == lesson_id,
            )
        )
        return None if result_id is None else self.result(project_id, lesson_id, result_id)

    def prompt_text(self, prompt_version_id: UUID) -> str | None:
        return self._session.scalar(
            select(CreationPromptVersion.business_prompt).where(
                CreationPromptVersion.id == prompt_version_id,
                CreationPromptVersion.organization_id == self._actor.organization_id,
            )
        )

    def persist_result(
        self,
        routing: VideoCreationRouting,
        job_id: UUID,
        file_version_id: UUID,
        output: dict[str, object],
        *,
        now: datetime,
    ) -> None:
        item, batch = self._locked_context(routing)
        self._session.add(
            GenerationResult(
                id=new_uuid7(),
                organization_id=self._actor.organization_id,
                creation_item_id=item.id,
                generation_job_id=job_id,
                candidate_no=1,
                status="available",
                file_asset_version_id=file_version_id,
                output_json=output,
                created_at=now,
            )
        )
        item.status = "review_required"
        item.updated_by = self._actor.principal_id
        item.lock_version += 1
        batch.status = "completed"
        batch.updated_by = self._actor.principal_id
        batch.lock_version += 1

    def mark_failure(self, routing: VideoCreationRouting) -> None:
        item, batch = self._locked_context(routing)
        item.status = "failed"
        batch.status = "partially_completed"
        self._touch(item, batch)

    def mark_cancelled(self, routing: VideoCreationRouting) -> None:
        item, batch = self._locked_context(routing)
        item.status = "ready"
        batch.status = "ready"
        self._touch(item, batch)

    def _package(self, data: VideoCreationInput, *, now: datetime) -> CreationPackage:
        content = _content(data)
        return CreationPackage(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            package_key=f"video.golden:{data.node_run_id}:{data.selection_id}",
            source_project_id=data.project_id,
            source_workflow_run_id=data.workflow_run_id,
            source_node_run_id=data.node_run_id,
            source_artifact_version_id=data.artifact_version_id,
            lesson_unit_id=data.lesson_id,
            context_snapshot_id=data.context_snapshot_id,
            source_prompt_snapshot_id=data.prompt_snapshot_id,
            package_type="video",
            status="ready",
            target_rules_json={
                "replace_modes": ["reject_if_occupied", "replace_active"],
                "allow_download": True,
            },
            content_hash=canonical_content_hash(content),
            created_at=now,
            created_by=self._actor.principal_id,
        )

    def _package_item(self, package_id: UUID, data: VideoCreationInput) -> CreationPackageItem:
        content = _content(data)
        return CreationPackageItem(
            id=new_uuid7(),
            creation_package_id=package_id,
            item_key="video.intro.candidate",
            position=1,
            title="课堂导入短片",
            business_prompt=data.business_prompt,
            prompt_json=content,
            reference_asset_version_ids=[str(data.keyframe_version_id)],
            reference_assets_json=[
                {"asset_version_id": str(data.keyframe_version_id), "role": "shot_keyframe"}
            ],
            output_spec_json={
                "mime_type": "video/mp4",
                "duration_seconds": 6,
                "candidate_count": 1,
            },
            target_slot_key=data.target_slot_key,
            consistency_key=_STYLE_KEY,
            content_hash=canonical_content_hash(content),
        )

    def _batch(self, package_id: UUID, data: VideoCreationInput) -> CreationBatch:
        return CreationBatch(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            owner_user_id=self._actor.user_id,
            source_kind="project",
            creation_package_id=package_id,
            source_project_id=data.project_id,
            source_workflow_run_id=data.workflow_run_id,
            source_node_run_id=data.node_run_id,
            studio_type="video",
            title="课堂导入短片",
            status="running",
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )

    def _item(self, batch_id: UUID, package_item: CreationPackageItem) -> CreationItem:
        return CreationItem(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            creation_batch_id=batch_id,
            creation_package_item_id=package_item.id,
            item_key=package_item.item_key,
            title=package_item.title,
            status="generating",
            target_slot_key=package_item.target_slot_key,
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )

    def _prompt(
        self, item_id: UUID, package_item: CreationPackageItem, keyframe_id: UUID, *, now: datetime
    ) -> CreationPromptVersion:
        prompt_hash = canonical_request_hash(
            {
                "business_prompt": package_item.business_prompt,
                "reference_asset_version_ids": [str(keyframe_id)],
                "output_spec": package_item.output_spec_json,
                "generation_profile": "quality",
            }
        )
        return CreationPromptVersion(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            creation_item_id=item_id,
            version_no=1,
            business_prompt=package_item.business_prompt,
            reference_asset_version_ids=[str(keyframe_id)],
            output_spec_json=package_item.output_spec_json,
            generation_profile="quality",
            content_hash=prompt_hash,
            created_at=now,
            created_by=self._actor.principal_id,
        )

    def _locked_context(self, routing: VideoCreationRouting) -> tuple[CreationItem, CreationBatch]:
        row = self._session.execute(
            select(CreationItem, CreationBatch)
            .join(CreationPromptVersion, CreationPromptVersion.creation_item_id == CreationItem.id)
            .join(CreationBatch, CreationBatch.id == CreationItem.creation_batch_id)
            .where(
                CreationPromptVersion.id == routing.prompt_version_id,
                CreationPromptVersion.organization_id == self._actor.organization_id,
                CreationBatch.id == routing.batch_id,
                CreationBatch.organization_id == self._actor.organization_id,
            )
            .with_for_update(of=(CreationItem, CreationBatch))
        ).one_or_none()
        if row is None:
            raise RuntimeError("VIDEO_CREATION_CONTEXT_INVALID")
        return row[0], row[1]

    def _touch(self, item: CreationItem, batch: CreationBatch) -> None:
        item.updated_by = self._actor.principal_id
        item.lock_version += 1
        batch.updated_by = self._actor.principal_id
        batch.lock_version += 1


_STYLE_KEY = "style.primary_math.paper_clay"


def _content(data: VideoCreationInput) -> dict[str, object]:
    return {
        "intro_selection_id": str(data.selection_id),
        "intro_snapshot": data.selection_snapshot,
        "style_key": _STYLE_KEY,
        "duration_seconds": 6,
    }


def _result_fact(result: GenerationResult, item: CreationItem) -> VideoResultFacts | None:
    if result.file_asset_version_id is None or item.target_slot_key is None:
        return None
    return VideoResultFacts(
        result_id=result.id,
        generation_job_id=result.generation_job_id,
        file_version_id=result.file_asset_version_id,
        target_slot_key=item.target_slot_key,
        active_adoption_id=item.active_adoption_id,
        status=result.status,
    )
