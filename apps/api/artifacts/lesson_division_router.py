"""Exact project lesson-division Artifact recovery query."""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from apps.api.artifact_quality.contracts import LessonPlanQualityReportFact
from apps.api.artifact_quality.repository import ArtifactQualityReportRepository
from apps.api.artifacts.presentation import serialize_approval, serialize_artifact
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.schemas import (
    LessonDivisionArtifactEnvelope,
    LessonDivisionArtifactRead,
    LessonPlanQualityReportRead,
)
from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService

router = APIRouter(tags=["artifacts"])


@router.get(
    "/api/v2/projects/{project_id}/lesson-division/artifact",
    response_model=LessonDivisionArtifactEnvelope,
    operation_id="getLessonDivisionArtifact",
)
def get_lesson_division_artifact(
    project_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> LessonDivisionArtifactEnvelope:
    ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    artifact = ArtifactRepository(session, actor).get_by_key(project_id, "lesson-division")
    if artifact is not None and (
        artifact.lesson_unit_id is not None
        or artifact.branch_key != "project"
        or artifact.artifact_type != "lesson_division"
    ):
        raise ApiError(
            status_code=409,
            code="LESSON_DIVISION_ARTIFACT_CONFLICT",
            message="The project lesson-division Artifact is incompatible.",
        )
    version_id = (
        artifact.current_submitted_version_id or artifact.current_approved_version_id
        if artifact is not None
        else None
    )
    approval = (
        ArtifactRepository(session, actor).latest_approval(version_id)
        if version_id is not None
        else None
    )
    quality_report = (
        ArtifactQualityReportRepository(session, actor).latest_project_artifact_fact(
            project_id=project_id,
            artifact_version_id=version_id,
        )
        if version_id is not None
        else None
    )
    return LessonDivisionArtifactEnvelope(
        data=LessonDivisionArtifactRead(
            artifact=(serialize_artifact(session, actor, artifact) if artifact else None),
            quality_report=(
                _serialize_quality_report(quality_report) if quality_report is not None else None
            ),
            latest_approval=(serialize_approval(approval) if approval else None),
        ),
        request_id=request.state.request_id,
    )


def _serialize_quality_report(report: LessonPlanQualityReportFact) -> LessonPlanQualityReportRead:
    return LessonPlanQualityReportRead(
        id=report.id,
        artifact_version_id=report.artifact_version_id,
        validate_node_run_id=report.validate_node_run_id,
        conclusion=cast(Literal["passed", "failed"], report.conclusion),
        findings=report.findings,
        evidence_hash=report.evidence_hash,
        created_at=report.created_at,
    )
