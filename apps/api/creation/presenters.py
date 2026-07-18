"""Creation model projections matching the public contract."""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID

from apps.api.creation.models import (
    Adoption,
    CreationBatch,
    CreationItem,
    CreationPromptVersion,
)
from apps.api.creation.schemas import (
    AdoptionRead,
    CreationPackageSourceRead,
    ProjectCreationBatchRead,
    ProjectCreationItemRead,
    PromptVersionRead,
    StandaloneCreationBatchRead,
    StandaloneCreationItemRead,
    StudioType,
)


def present_batch(
    batch: CreationBatch,
    items: list[CreationItem],
) -> ProjectCreationBatchRead | StandaloneCreationBatchRead:
    if batch.source_kind == "project":
        if (
            batch.creation_package_id is None
            or batch.source_project_id is None
            or batch.source_workflow_run_id is None
            or batch.source_node_run_id is None
        ):
            raise ValueError("project creation batch source is incomplete")
        return ProjectCreationBatchRead(
            id=batch.id,
            source_kind="project",
            creation_package_id=batch.creation_package_id,
            source=CreationPackageSourceRead(
                project_id=batch.source_project_id,
                workflow_run_id=batch.source_workflow_run_id,
                source_node_run_id=batch.source_node_run_id,
            ),
            studio_type=cast(StudioType, batch.studio_type),
            title=batch.title,
            status=batch.status,
            items=[
                ProjectCreationItemRead(
                    id=item.id,
                    item_key=item.item_key,
                    title=item.title,
                    status=item.status,
                    current_prompt_version_id=item.current_prompt_version_id,
                    active_adoption_id=item.active_adoption_id,
                    target_slot_key=_required_target(item),
                )
                for item in items
            ],
        )
    return StandaloneCreationBatchRead(
        id=batch.id,
        source_kind="standalone",
        studio_type=cast(StudioType, batch.studio_type),
        title=batch.title,
        status=batch.status,
        items=[
            StandaloneCreationItemRead(
                id=item.id,
                item_key=item.item_key,
                title=item.title,
                status=item.status,
                current_prompt_version_id=item.current_prompt_version_id,
                active_adoption_id=item.active_adoption_id,
            )
            for item in items
        ],
    )


def present_prompt(version: CreationPromptVersion) -> PromptVersionRead:
    return PromptVersionRead(
        id=version.id,
        creation_item_id=version.creation_item_id,
        version_no=version.version_no,
        business_prompt=version.business_prompt,
        reference_asset_version_ids=[UUID(value) for value in version.reference_asset_version_ids],
        output_spec=version.output_spec_json,
        generation_profile=cast(
            Literal["quality", "balanced", "speed"], version.generation_profile
        ),
        content_hash=version.content_hash,
        created_at=version.created_at,
    )


def present_adoption(adoption: Adoption) -> AdoptionRead:
    return AdoptionRead(
        id=adoption.id,
        creation_item_id=adoption.creation_item_id,
        generation_result_id=adoption.generation_result_id,
        adoption_mode=cast(Literal["teacher", "automation_policy"], adoption.adoption_mode),
        reason=adoption.reason,
        adopted_at=adoption.adopted_at,
    )


def _required_target(item: CreationItem) -> str:
    if item.target_slot_key is None:
        raise ValueError("project creation item target is missing")
    return item.target_slot_key
