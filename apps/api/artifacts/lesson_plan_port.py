"""Artifact-owned facts for the lesson-plan runtime application service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.artifact_quality.contracts import QualitySource
from apps.api.artifacts.models import Artifact, ArtifactVersion
from apps.api.artifacts.quality_gate import ArtifactQualityApprovalGuard
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.content_runtime.approval_port import ContentDefinitionApprovalReader
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.lessons.approval_port import LessonApprovalReader


@dataclass(frozen=True, slots=True)
class ReviewableLessonPlanFact:
    artifact_id: UUID
    artifact_version_id: UUID
    project_id: UUID
    lesson_unit_id: UUID
    lesson_key: str
    content_definition_key: str
    content_release_id: UUID
    workflow_definition_version_id: UUID
    lineage_node_run_id: UUID
    lineage_artifact_version_id: UUID
    division: QualitySource
    division_context_snapshot_id: UUID
    content_hash: str
    content: dict[str, Any]


class ArtifactLessonPlanReader:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor

    def require_reviewable(self, artifact_version_id: UUID) -> ReviewableLessonPlanFact:
        record = ArtifactRepository(self._session, self._actor).get_version(artifact_version_id)
        if record is None:
            raise self._not_found()
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
            definition_key != "lesson_plan.generate.output"
            or artifact.artifact_type != "lesson_plan"
            or artifact.branch_key != "lesson_plan"
            or artifact.lesson_unit_id is None
            or artifact.status != "in_review"
            or artifact.current_submitted_version_id != version.id
        ):
            raise self._invalid("The submitted artifact is not an exact lesson plan.")
        lesson = LessonApprovalReader(self._session, self._actor).current_lesson(
            project_id=artifact.project_id,
            lesson_unit_id=artifact.lesson_unit_id,
        )
        if lesson is None:
            raise self._invalid("The target lesson has no approved division source.")
        lineage = self._generated_lineage(artifact.id, version.version_no)
        division, division_context_snapshot_id = self._approved_division(
            project_id=artifact.project_id,
            version_id=lesson.source_division_version_id,
        )
        return ReviewableLessonPlanFact(
            artifact_id=artifact.id,
            artifact_version_id=version.id,
            project_id=artifact.project_id,
            lesson_unit_id=lesson.id,
            lesson_key=lesson.lesson_key,
            content_definition_key=definition_key,
            content_release_id=project.content_release_id,
            workflow_definition_version_id=project.workflow_definition_version_id,
            lineage_node_run_id=cast(UUID, lineage.source_node_run_id),
            lineage_artifact_version_id=lineage.id,
            division=division,
            division_context_snapshot_id=division_context_snapshot_id,
            content_hash=version.content_hash,
            content=version.content_json,
        )

    def require_quality_evidence(self, artifact_version_id: UUID) -> dict[str, str]:
        record = ArtifactRepository(self._session, self._actor).get_version(artifact_version_id)
        if record is None:
            raise self._not_found()
        version, artifact = record
        project = ProjectAccessService(self._session, self._actor).require(
            artifact.project_id,
            ProjectAction.REVIEW,
            for_update=True,
        )
        return ArtifactQualityApprovalGuard(self._session, self._actor).require_evidence(
            artifact,
            version,
            content_release_id=project.content_release_id,
            workflow_definition_version_id=project.workflow_definition_version_id,
        )

    def _generated_lineage(self, artifact_id: UUID, maximum_version_no: int) -> ArtifactVersion:
        version = self._session.scalar(
            select(ArtifactVersion)
            .where(
                ArtifactVersion.artifact_id == artifact_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                ArtifactVersion.version_no <= maximum_version_no,
                ArtifactVersion.source_node_run_id.is_not(None),
                ArtifactVersion.context_snapshot_id.is_not(None),
            )
            .order_by(ArtifactVersion.version_no.desc())
            .limit(1)
        )
        if (
            version is None
            or version.source_node_run_id is None
            or version.context_snapshot_id is None
        ):
            raise self._invalid("The lesson plan has no generated fixed-release lineage.")
        return version

    def _approved_division(
        self,
        *,
        project_id: UUID,
        version_id: UUID,
    ) -> tuple[QualitySource, UUID]:
        row = self._session.execute(
            select(ArtifactVersion, Artifact)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                ArtifactVersion.id == version_id,
                ArtifactVersion.organization_id == self._actor.organization_id,
                Artifact.organization_id == self._actor.organization_id,
                Artifact.project_id == project_id,
                Artifact.lesson_unit_id.is_(None),
                Artifact.branch_key == "project",
                Artifact.artifact_type == "lesson_division",
                Artifact.current_approved_version_id == version_id,
                Artifact.status == "approved",
                Artifact.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None:
            raise self._invalid("The current approved lesson division is unavailable.")
        version, artifact = row
        if version.context_snapshot_id is None:
            raise self._invalid("The approved lesson division context is unavailable.")
        return (
            QualitySource(
                source_type="artifact",
                source_id=artifact.id,
                source_version_id=version.id,
                content_hash=version.content_hash,
                content=version.content_json,
                schema=None,
            ),
            version.context_snapshot_id,
        )

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(status_code=404, code="ARTIFACT_NOT_FOUND", message="Not found.")

    @staticmethod
    def _invalid(message: str) -> ApiError:
        return ApiError(status_code=409, code="LESSON_PLAN_RUNTIME_INVALID", message=message)
