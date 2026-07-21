"""Artifact-owned facts used by the lesson-division application service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.models import ArtifactVersion
from apps.api.artifacts.quality_gate import ArtifactQualityApprovalGuard
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.content_runtime.approval_port import ContentDefinitionApprovalReader
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService


@dataclass(frozen=True, slots=True)
class GeneratedLessonDivisionFact:
    artifact_id: UUID
    artifact_version_id: UUID
    project_id: UUID
    content_definition_key: str
    content_release_id: UUID
    workflow_definition_version_id: UUID
    source_node_run_id: UUID
    context_snapshot_id: UUID
    content_hash: str
    content: dict[str, Any]


class ArtifactLessonDivisionReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require_generated(self, artifact_version_id: UUID) -> GeneratedLessonDivisionFact:
        record = ArtifactRepository(self._session, self._actor).get_version(artifact_version_id)
        if record is None:
            raise ApiError(status_code=404, code="ARTIFACT_NOT_FOUND", message="Not found.")
        version, artifact = record
        project = ProjectAccessService(self._session, self._actor).require(
            artifact.project_id,
            ProjectAction.GENERATE,
        )
        definition_key = ContentDefinitionApprovalReader(self._session).definition_key(
            definition_id=artifact.content_definition_version_id,
            content_release_id=project.content_release_id,
        )
        if (
            definition_key is None
            or version.source_node_run_id is None
            or version.context_snapshot_id is None
        ):
            raise self._invalid("The generated artifact has incomplete fixed-release lineage.")
        return GeneratedLessonDivisionFact(
            artifact_id=artifact.id,
            artifact_version_id=version.id,
            project_id=artifact.project_id,
            content_definition_key=definition_key,
            content_release_id=project.content_release_id,
            workflow_definition_version_id=project.workflow_definition_version_id,
            source_node_run_id=version.source_node_run_id,
            context_snapshot_id=version.context_snapshot_id,
            content_hash=version.content_hash,
            content=version.content_json,
        )

    def require_quality_evidence(self, artifact_version_id: UUID) -> None:
        record = ArtifactRepository(self._session, self._actor).get_version(artifact_version_id)
        if record is None:
            raise ApiError(status_code=404, code="ARTIFACT_NOT_FOUND", message="Not found.")
        version, artifact = record
        project = ProjectAccessService(self._session, self._actor).require(
            artifact.project_id,
            ProjectAction.REVIEW,
            for_update=True,
        )
        ArtifactQualityApprovalGuard(self._session, self._actor).require_evidence(
            artifact,
            version,
            content_release_id=project.content_release_id,
            workflow_definition_version_id=project.workflow_definition_version_id,
        )

    def previous_content(self, version_id: UUID | None) -> dict[str, Any] | None:
        if version_id is None:
            return None
        version = self._session.get(ArtifactVersion, version_id)
        if version is None or version.organization_id != self._actor.organization_id:
            raise self._invalid("The previous approved lesson division is unavailable.")
        return version.content_json

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(
            status_code=409,
            code="LESSON_DIVISION_RUNTIME_INVALID",
            message=message,
        )
