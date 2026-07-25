"""Project-singleton material-scope version command."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.authoring_provision import ArtifactAuthoringProvisionPort
from apps.api.artifacts.models import Artifact
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.schemas import CreateMaterialScopeVersionRequest
from apps.api.artifacts.service import ArtifactService
from apps.api.artifacts.validation import ArtifactValidation
from apps.api.assets.models import MaterialParseVersion
from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageVersion,
    ContentReleaseItem,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction, system_actor
from apps.api.projects.models import Project
from apps.api.uploads.models import SourceMaterial

MATERIAL_SCOPE_DEFINITION_KEY = "material.scope_review.output"
MATERIAL_SCOPE_ARTIFACT_KEY = "material-scope"


class MaterialScopeVersionService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._artifacts = ArtifactRepository(session, actor)
        self._validation = ArtifactValidation(session, actor)

    def create(
        self,
        project_id: UUID,
        payload: CreateMaterialScopeVersionRequest,
        *,
        request_id: str | None,
    ) -> Artifact:
        project = self._validation.require_project(
            project_id,
            ProjectAction.EDIT,
            for_update=True,
        )
        material, parsed = self._require_source(project, payload)
        evidence_keys = self._evidence_keys(parsed, payload.page_start, payload.page_end)
        definition = self._require_definition(project)
        content = self._content(project, material, parsed, payload, evidence_keys)
        artifact = self._artifacts.get_by_key(project.id, MATERIAL_SCOPE_ARTIFACT_KEY)
        service = ArtifactService(self._session, self._actor)
        if artifact is None:
            artifact = service.create(
                project.id,
                artifact_key=MATERIAL_SCOPE_ARTIFACT_KEY,
                artifact_type="material_scope",
                branch_key="project",
                content_definition_version_id=definition.id,
                draft_branch="main",
                initial_content={
                    key: value
                    for key, value in content.items()
                    if key
                    not in {
                        "source_material_id",
                        "material_parse_version_id",
                        "page_start",
                        "page_end",
                    }
                },
                request_id=request_id,
            )
        self._require_singleton_identity(artifact, project, definition)
        locked_fields = {
            "source_material_id": str(material.id),
            "material_parse_version_id": str(parsed.id),
            "page_start": payload.page_start,
            "page_end": payload.page_end,
        }
        draft = ArtifactAuthoringProvisionPort(
            self._session,
            system_actor(self._actor.organization_id),
        ).replace_material_scope_draft(
            artifact_id=artifact.id,
            draft_branch="main",
            content=content,
            locked_fields=locked_fields,
        )
        service.submit(
            artifact.id,
            "main",
            expected_lock_version=draft.lock_version,
            source_kind="manual",
            request_id=request_id,
        )
        return artifact

    def _require_source(
        self,
        project: Project,
        payload: CreateMaterialScopeVersionRequest,
    ) -> tuple[SourceMaterial, MaterialParseVersion]:
        material = self._session.scalar(
            select(SourceMaterial).where(
                SourceMaterial.id == payload.source_material_id,
                SourceMaterial.organization_id == self._actor.organization_id,
                SourceMaterial.project_id == project.id,
                SourceMaterial.deleted_at.is_(None),
            )
        )
        parsed = self._session.scalar(
            select(MaterialParseVersion).where(
                MaterialParseVersion.id == payload.material_parse_version_id,
                MaterialParseVersion.organization_id == self._actor.organization_id,
                MaterialParseVersion.source_material_id == payload.source_material_id,
            )
        )
        if material is None or parsed is None:
            raise ApiError(
                status_code=404,
                code="MATERIAL_SCOPE_SOURCE_NOT_FOUND",
                message="The material-scope source was not found.",
            )
        if parsed.status != "succeeded":
            raise ApiError(
                status_code=409,
                code="MATERIAL_PARSE_NOT_READY",
                message="The material parse has not succeeded.",
            )
        if (
            parsed.page_count is None
            or payload.page_start > payload.page_end
            or payload.page_end > parsed.page_count
        ):
            raise self._invalid("The material-scope page range is invalid.")
        return material, parsed

    def _evidence_keys(
        self,
        parsed: MaterialParseVersion,
        page_start: int,
        page_end: int,
    ) -> list[str]:
        content = parsed.content_json
        raw_pages = content.get("pages") if isinstance(content, Mapping) else None
        if not isinstance(raw_pages, Sequence) or isinstance(raw_pages, (str, bytes)):
            raise self._invalid("The material parse evidence is unavailable.")
        pages: dict[int, Mapping[str, Any]] = {}
        for value in raw_pages:
            if not isinstance(value, Mapping):
                raise self._invalid("The material parse evidence is unavailable.")
            page_number = value.get("page_number")
            if type(page_number) is not int or page_number in pages:
                raise self._invalid("The material parse evidence is unavailable.")
            pages[cast(int, page_number)] = cast(Mapping[str, Any], value)
        selected_numbers = list(range(page_start, page_end + 1))
        if any(page_number not in pages for page_number in selected_numbers):
            raise self._invalid("The selected physical pages are unavailable.")
        keys: list[str] = []
        seen: set[str] = set()
        for page_number in selected_numbers:
            page = pages[page_number]
            for collection_name, key_name in (
                ("text_blocks", "block_id"),
                ("image_references", "image_id"),
            ):
                values = page.get(collection_name)
                if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                    raise self._invalid("The material parse evidence is unavailable.")
                page_keys = sorted(
                    value.get(key_name)
                    for value in values
                    if isinstance(value, Mapping) and isinstance(value.get(key_name), str)
                )
                for key in page_keys:
                    if key and key not in seen:
                        keys.append(key)
                        seen.add(key)
        if not keys:
            raise self._invalid("The selected physical pages contain no evidence.")
        return keys

    def _require_definition(self, project: Project) -> ContentDefinitionVersion:
        definitions = list(
            self._session.scalars(
                select(ContentDefinitionVersion)
                .join(
                    ContentPackageVersion,
                    ContentPackageVersion.id == ContentDefinitionVersion.content_package_version_id,
                )
                .join(
                    ContentReleaseItem,
                    ContentReleaseItem.content_package_version_id == ContentPackageVersion.id,
                )
                .where(
                    ContentReleaseItem.content_release_id == project.content_release_id,
                    ContentPackageVersion.status == "published",
                    ContentDefinitionVersion.definition_key == MATERIAL_SCOPE_DEFINITION_KEY,
                )
            )
        )
        if len(definitions) != 1:
            raise self._invalid("The published material-scope definition is unavailable.")
        return definitions[0]

    @staticmethod
    def _content(
        project: Project,
        material: SourceMaterial,
        parsed: MaterialParseVersion,
        payload: CreateMaterialScopeVersionRequest,
        evidence_keys: list[str],
    ) -> dict[str, Any]:
        return {
            "source_material_id": str(material.id),
            "material_parse_version_id": str(parsed.id),
            "knowledge_point": project.knowledge_point,
            "knowledge_boundary": {
                "allowed": [project.knowledge_point],
                "forbidden": [f"超出{project.knowledge_point}及所选教材页段的内容"],
            },
            "approved_evidence_keys": evidence_keys,
            "page_start": payload.page_start,
            "page_end": payload.page_end,
            "duration_minutes": 40,
            "lesson_count_mode": "auto",
            "lesson_type_preferences": [],
            "special_requirements": "",
        }

    @staticmethod
    def _require_singleton_identity(
        artifact: Artifact,
        project: Project,
        definition: ContentDefinitionVersion,
    ) -> None:
        if (
            artifact.project_id != project.id
            or artifact.lesson_unit_id is not None
            or artifact.branch_key != "project"
            or artifact.artifact_key != MATERIAL_SCOPE_ARTIFACT_KEY
            or artifact.artifact_type != "material_scope"
            or artifact.content_definition_version_id != definition.id
        ):
            raise ApiError(
                status_code=409,
                code="MATERIAL_SCOPE_CONFLICT",
                message="The project material-scope singleton is incompatible.",
            )

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=422, code="INVALID_MATERIAL_SCOPE", message=message)
