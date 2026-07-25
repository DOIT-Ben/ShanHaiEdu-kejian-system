"""Exact lesson-plan Artifact recovery query."""

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
    LessonPlanArtifactEnvelope,
    LessonPlanArtifactRead,
    LessonPlanQualityReportRead,
)
from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService

router = APIRouter(tags=["artifacts"])


@router.get(
    "/api/v2/projects/{project_id}/lessons/{lesson_id}/lesson-plan/artifact",
    response_model=LessonPlanArtifactEnvelope,
    operation_id="getLessonPlanArtifact",
)
def get_lesson_plan_artifact(
    project_id: UUID,
    lesson_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> LessonPlanArtifactEnvelope:
    ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    artifacts = ArtifactRepository(session, actor).lesson_plan_for_lesson(
        project_id,
        lesson_id,
    )
    if len(artifacts) > 1:
        raise ApiError(
            status_code=409,
            code="LESSON_PLAN_ARTIFACT_AMBIGUOUS",
            message="The lesson has more than one active lesson-plan Artifact.",
        )
    artifact = artifacts[0] if artifacts else None
    if artifact is None:
        data = LessonPlanArtifactRead(
            artifact=None,
            quality_report=None,
            latest_approval=None,
        )
        return LessonPlanArtifactEnvelope(data=data, request_id=request.state.request_id)

    version_id = artifact.current_submitted_version_id or artifact.current_approved_version_id
    quality_report = (
        ArtifactQualityReportRepository(session, actor).latest_lesson_plan_fact(
            project_id=project_id,
            lesson_unit_id=lesson_id,
            artifact_version_id=version_id,
        )
        if version_id is not None
        else None
    )
    approval = (
        ArtifactRepository(session, actor).latest_approval(version_id)
        if version_id is not None
        else None
    )
    return LessonPlanArtifactEnvelope(
        data=LessonPlanArtifactRead(
            artifact=serialize_artifact(session, actor, artifact),
            quality_report=(
                _serialize_quality_report(quality_report) if quality_report is not None else None
            ),
            latest_approval=(serialize_approval(approval) if approval is not None else None),
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
