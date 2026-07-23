"""Prepare the approved material scope required by lesson division."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.authoring_provision import ArtifactAuthoringProvisionPort
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.service import ArtifactService
from apps.api.assets.material_evidence import page_block_evidence_keys
from apps.api.assets.repository import FileAssetRepository
from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageVersion,
    ContentReleaseItem,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction, system_actor
from apps.api.identity.permissions import ProjectAccessService
from apps.api.lessons.runtime_service import LessonDivisionRuntimeService


@dataclass(frozen=True, slots=True)
class MaterialScopePreparation:
    material_scope_artifact_id: UUID
    material_scope_version_id: UUID
    generate_node_run_id: UUID
    validate_node_run_id: UUID
    gate_node_run_id: UUID


class MaterialScopePreparationService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def prepare(
        self,
        project_id: UUID,
        *,
        material_id: UUID,
        material_parse_version_id: UUID,
        page_start: int,
        page_end: int,
        duration_minutes: int,
        requested_lesson_count: int | None,
        special_requirements: str,
        request_id: str,
    ) -> MaterialScopePreparation:
        project = ProjectAccessService(self._session, self._actor).require(
            project_id,
            ProjectAction.GENERATE,
            for_update=True,
        )
        parse = FileAssetRepository(
            self._session,
            self._actor,
        ).get_succeeded_parse_for_project(
            project_id,
            material_id,
            material_parse_version_id,
        )
        if parse is None or parse.content_json is None:
            raise _invalid_pages("The selected material parse is unavailable.")
        evidence_keys = page_block_evidence_keys(
            parse.content_json,
            page_start=page_start,
            page_end=page_end,
        )
        if not evidence_keys:
            raise _invalid_pages("The selected physical pages have no complete text evidence.")

        definition_id = self._material_scope_definition(
            project.content_release_id,
        )
        service = ArtifactService(self._session, self._actor)
        lesson_count_mode = "specified" if requested_lesson_count is not None else "auto"
        knowledge_point = project.knowledge_point or "所选教材页内容"
        initial_content: dict[str, Any] = {
            "knowledge_point": knowledge_point,
            "knowledge_boundary": {
                "allowed": [knowledge_point],
                "forbidden": ["不得超出所选教材页和当前知识点"],
            },
            "approved_evidence_keys": list(evidence_keys),
            "duration_minutes": duration_minutes,
            "lesson_count_mode": lesson_count_mode,
            "lesson_type_preferences": ["new_learning"],
            "special_requirements": special_requirements,
        }
        if requested_lesson_count is not None:
            initial_content["requested_lesson_count"] = requested_lesson_count
        artifact = service.create(
            project.id,
            artifact_key="material-scope",
            artifact_type="material_scope",
            branch_key="project",
            content_definition_version_id=definition_id,
            draft_branch="main",
            initial_content=initial_content,
            request_id=request_id,
        )
        draft = ArtifactRepository(self._session, self._actor).get_draft(artifact.id, "main")
        if draft is None:
            raise _invalid_pages("The material-scope draft was not created.")
        provisioned = ArtifactAuthoringProvisionPort(
            self._session,
            system_actor(self._actor.organization_id),
        ).provision_initial_locked_fields(
            artifact_id=artifact.id,
            draft_branch="main",
            expected_lock_version=draft.lock_version,
            fields={
                "source_material_id": str(material_id),
                "material_parse_version_id": str(material_parse_version_id),
                "page_start": page_start,
                "page_end": page_end,
            },
        )
        version = service.submit(
            artifact.id,
            "main",
            expected_lock_version=provisioned.lock_version,
            source_kind="manual",
            request_id=request_id,
        )
        service.review(
            version.id,
            action="approve",
            comment="Teacher selected the material pages for lesson planning.",
            request_id=request_id,
        )
        nodes = LessonDivisionRuntimeService(self._session, self._actor).initialize(project.id)
        return MaterialScopePreparation(
            material_scope_artifact_id=artifact.id,
            material_scope_version_id=version.id,
            generate_node_run_id=nodes.generate_node_run_id,
            validate_node_run_id=nodes.validate_node_run_id,
            gate_node_run_id=nodes.approve_node_run_id,
        )

    def _material_scope_definition(self, content_release_id: UUID) -> UUID:
        definitions = list(
            self._session.scalars(
                select(ContentDefinitionVersion)
                .join(
                    ContentPackageVersion,
                    ContentPackageVersion.id
                    == ContentDefinitionVersion.content_package_version_id,
                )
                .join(
                    ContentReleaseItem,
                    ContentReleaseItem.content_package_version_id == ContentPackageVersion.id,
                )
                .where(
                    ContentReleaseItem.content_release_id == content_release_id,
                    ContentPackageVersion.status == "published",
                    ContentDefinitionVersion.definition_key == "material.scope_review.output",
                )
            )
        )
        if len(definitions) != 1:
            raise ApiError(
                status_code=409,
                code="MATERIAL_SCOPE_DEFINITION_UNAVAILABLE",
                message="The fixed material-scope definition is unavailable.",
            )
        return definitions[0].id


def _invalid_pages(message: str) -> ApiError:
    return ApiError(
        status_code=422,
        code="MATERIAL_SCOPE_PAGES_INVALID",
        message=message,
    )
