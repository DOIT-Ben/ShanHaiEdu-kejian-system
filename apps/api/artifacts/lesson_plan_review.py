"""Open the declared workflow gate before exact Artifact approval."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.approval_service import ArtifactApprovalService
from apps.api.artifacts.domain import ApprovalAction
from apps.api.content_runtime.approval_port import ContentDefinitionApprovalReader
from apps.api.identity.context import ActorContext
from apps.api.intro_options.runtime import IntroOptionRuntimeService
from apps.api.lessons.lesson_plan_runtime import LessonPlanRuntimeService
from apps.api.lessons.runtime_service import LessonDivisionRuntimeService
from apps.api.projects.repository import ProjectRepository


def open_lesson_plan_approval_gate(
    session: Session,
    actor: ActorContext,
    artifact_version_id: UUID,
    action: str,
) -> None:
    resolved_action, version, artifact = ArtifactApprovalService(
        session,
        actor,
    ).require_access(
        artifact_version_id,
        action=action,
        for_update=True,
    )
    if (
        resolved_action is not ApprovalAction.APPROVE
        or artifact.current_approved_version_id == version.id
    ):
        return
    project = ProjectRepository(session, actor).get(artifact.project_id)
    if project is None:
        return
    definition_key = ContentDefinitionApprovalReader(session).definition_key(
        definition_id=artifact.content_definition_version_id,
        content_release_id=project.content_release_id,
    )
    if artifact.artifact_type == "lesson_plan" and definition_key == "lesson_plan.generate.output":
        LessonPlanRuntimeService(session, actor).open_approval(artifact_version_id)
    elif (
        artifact.artifact_type == "lesson_division"
        and definition_key == "lesson.division.generate.output"
    ):
        LessonDivisionRuntimeService(session, actor).open_approval(artifact_version_id)
    elif (
        artifact.artifact_type == "intro_option_set"
        and definition_key == "intro.generate_options.output"
    ):
        IntroOptionRuntimeService(session, actor).open_approval(artifact_version_id)
