"""Artifact access, schema, and provenance validation helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifacts.models import Artifact
from apps.api.content_runtime.definition_projection import validate_content_rules
from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackageVersion,
    ContentReleaseItem,
)
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.lessons.models import LessonUnit
from apps.api.projects.models import Project
from apps.api.workflows.models import NodeRun


class ArtifactValidation:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require_project(
        self,
        project_id: UUID,
        action: ProjectAction,
        *,
        for_update: bool = False,
    ) -> Project:
        if not self._actor.is_system:
            return ProjectAccessService(self._session, self._actor).require(
                project_id, action, for_update=for_update
            )
        statement = select(Project).where(
            Project.id == project_id,
            Project.organization_id == self._actor.organization_id,
            Project.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        project = self._session.scalar(statement)
        if project is None:
            raise self.not_found()
        return project

    def require_lesson(self, project_id: UUID, lesson_unit_id: UUID | None) -> None:
        if lesson_unit_id is None:
            return
        lesson = self._session.scalar(
            select(LessonUnit).where(
                LessonUnit.id == lesson_unit_id,
                LessonUnit.project_id == project_id,
                LessonUnit.organization_id == self._actor.organization_id,
                LessonUnit.deleted_at.is_(None),
            )
        )
        if lesson is None:
            raise self.not_found()

    def require_artifact_definition(self, artifact: Artifact) -> ContentDefinitionVersion:
        project = self._session.get(Project, artifact.project_id)
        if project is None:
            raise self.not_found()
        return self.require_definition(
            artifact.content_definition_version_id, project.content_release_id
        )

    def require_definition(
        self,
        definition_id: UUID,
        content_release_id: UUID,
    ) -> ContentDefinitionVersion:
        definition = self._session.scalar(
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
                ContentDefinitionVersion.id == definition_id,
                ContentReleaseItem.content_release_id == content_release_id,
                ContentPackageVersion.status == "published",
            )
        )
        if definition is None:
            raise self.invalid("The content definition version is unavailable.")
        return definition

    def validate_provenance(self, source_kind: str, source_node_run_id: UUID | None) -> None:
        if source_kind not in {"manual", "model", "import", "system"}:
            raise self.invalid("The artifact source kind is invalid.")
        if source_kind in {"model", "system"} and not self._actor.is_system:
            raise ApiError(
                status_code=403,
                code="PERMISSION_DENIED",
                message="System provenance can only be recorded by a system actor.",
            )
        if source_kind == "model" and source_node_run_id is None:
            raise self.invalid("Model-sourced artifact versions require a source node run.")

    def require_source_node(self, node_id: UUID | None) -> None:
        if node_id is None:
            return
        node = self._session.scalar(
            select(NodeRun).where(
                NodeRun.id == node_id,
                NodeRun.organization_id == self._actor.organization_id,
                NodeRun.deleted_at.is_(None),
            )
        )
        if node is None:
            raise self.invalid("The source node run is unavailable.")

    @staticmethod
    def validation_report(
        definition: ContentDefinitionVersion,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        validator = Draft202012Validator(definition.schema_json)
        schema_errors = sorted(
            validator.iter_errors(content),  # pyright: ignore[reportUnknownMemberType]
            key=lambda item: list(item.path),
        )
        errors = [
            {"path": [str(part) for part in error.path], "message": error.message}
            for error in schema_errors
        ]
        errors.extend(validate_content_rules(definition.validation_rules_json, content))
        return {
            "valid": not errors,
            "schema_id": str(definition.id),
            "errors": errors,
        }

    @staticmethod
    def not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="ARTIFACT_NOT_FOUND",
            message="The artifact resource was not found.",
        )

    @staticmethod
    def invalid(message: str) -> ApiError:
        return ApiError(status_code=422, code="INVALID_ARTIFACT", message=message)
