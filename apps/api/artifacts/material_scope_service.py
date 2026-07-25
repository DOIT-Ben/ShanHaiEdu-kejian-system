"""Project-singleton material-scope version command."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.authoring_provision import ArtifactAuthoringProvisionPort
from apps.api.artifacts.models import Artifact
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.schemas import CreateMaterialScopeVersionRequest
from apps.api.artifacts.service import ArtifactService
from apps.api.artifacts.validation import ArtifactValidation
from apps.api.assets.material_scope_port import (
    MaterialScopeSourceFact,
    MaterialScopeSourceReader,
)
from apps.api.content_runtime.definition_lookup_port import (
    PublishedContentDefinitionFact,
    PublishedContentDefinitionReader,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction, system_actor

MATERIAL_SCOPE_DEFINITION_KEY = "material.scope_review.output"
MATERIAL_SCOPE_ARTIFACT_KEY = "material-scope"


class MaterialScopeVersionService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._artifacts = ArtifactRepository(session, actor)
        self._validation = ArtifactValidation(session, actor)
        self._sources = MaterialScopeSourceReader(session, actor)
        self._definitions = PublishedContentDefinitionReader(session)

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
        source = self._require_source(project.id, payload)
        evidence_keys = self._evidence_keys(source, payload.page_start, payload.page_end)
        definition = self._require_definition(project.content_release_id)
        content = self._content(project.knowledge_point, source, payload, evidence_keys)
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
        self._require_singleton_identity(artifact, project.id, definition.id)
        locked_fields = {
            "source_material_id": str(source.material_id),
            "material_parse_version_id": str(source.parse_version_id),
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
        project_id: UUID,
        payload: CreateMaterialScopeVersionRequest,
    ) -> MaterialScopeSourceFact:
        source = self._sources.get(
            project_id=project_id,
            material_id=payload.source_material_id,
            parse_version_id=payload.material_parse_version_id,
        )
        if source is None:
            raise ApiError(
                status_code=404,
                code="MATERIAL_SCOPE_SOURCE_NOT_FOUND",
                message="The material-scope source was not found.",
            )
        if source.parse_status != "succeeded":
            raise ApiError(
                status_code=409,
                code="MATERIAL_PARSE_NOT_READY",
                message="The material parse has not succeeded.",
            )
        if (
            source.page_count is None
            or payload.page_start > payload.page_end
            or payload.page_end > source.page_count
        ):
            raise self._invalid("The material-scope page range is invalid.")
        return source

    def _evidence_keys(
        self,
        source: MaterialScopeSourceFact,
        page_start: int,
        page_end: int,
    ) -> list[str]:
        content = source.parse_content
        if not isinstance(content, Mapping):
            raise self._invalid("The material parse evidence is unavailable.")
        raw_pages = cast(Mapping[str, object], content).get("pages")
        if not isinstance(raw_pages, Sequence) or isinstance(raw_pages, (str, bytes)):
            raise self._invalid("The material parse evidence is unavailable.")
        pages: dict[int, Mapping[str, object]] = {}
        for value in cast(Sequence[object], raw_pages):
            if not isinstance(value, Mapping):
                raise self._invalid("The material parse evidence is unavailable.")
            page = cast(Mapping[str, object], value)
            page_number = page.get("page_number")
            if type(page_number) is not int or page_number in pages:
                raise self._invalid("The material parse evidence is unavailable.")
            pages[page_number] = page
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
                page_keys: list[str] = []
                for value in cast(Sequence[object], values):
                    if not isinstance(value, Mapping):
                        continue
                    key = cast(Mapping[str, object], value).get(key_name)
                    if isinstance(key, str):
                        page_keys.append(key)
                page_keys.sort()
                for key in page_keys:
                    if key and key not in seen:
                        keys.append(key)
                        seen.add(key)
        if not keys:
            raise self._invalid("The selected physical pages contain no evidence.")
        return sorted(keys)

    def _require_definition(self, content_release_id: UUID) -> PublishedContentDefinitionFact:
        definition = self._definitions.find_unique(
            content_release_id=content_release_id,
            definition_key=MATERIAL_SCOPE_DEFINITION_KEY,
        )
        if definition is None:
            raise self._invalid("The published material-scope definition is unavailable.")
        return definition

    @staticmethod
    def _content(
        knowledge_point: str,
        source: MaterialScopeSourceFact,
        payload: CreateMaterialScopeVersionRequest,
        evidence_keys: list[str],
    ) -> dict[str, Any]:
        return {
            "source_material_id": str(source.material_id),
            "material_parse_version_id": str(source.parse_version_id),
            "knowledge_point": knowledge_point,
            "knowledge_boundary": {
                "allowed": [knowledge_point],
                "forbidden": [f"超出{knowledge_point}及所选教材页段的内容"],
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
        project_id: UUID,
        definition_id: UUID,
    ) -> None:
        if (
            artifact.project_id != project_id
            or artifact.lesson_unit_id is not None
            or artifact.branch_key != "project"
            or artifact.artifact_key != MATERIAL_SCOPE_ARTIFACT_KEY
            or artifact.artifact_type != "material_scope"
            or artifact.content_definition_version_id != definition_id
        ):
            raise ApiError(
                status_code=409,
                code="MATERIAL_SCOPE_CONFLICT",
                message="The project material-scope singleton is incompatible.",
            )

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=422, code="INVALID_MATERIAL_SCOPE", message=message)
