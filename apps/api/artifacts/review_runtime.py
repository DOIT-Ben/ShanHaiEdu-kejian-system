"""Open declared R1 approval gates before Artifact approval."""

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
from apps.api.projects.models import Project


def open_r1_approval_gate(
    session: Session,
    actor: ActorContext,
    artifact_version_id: UUID,
    *,
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
    project = session.get(Project, artifact.project_id)
    definition_key = (
        ContentDefinitionApprovalReader(session).definition_key(
            definition_id=artifact.content_definition_version_id,
            content_release_id=project.content_release_id,
        )
        if project is not None
        else None
    )
    artifact_definition = (artifact.artifact_type, definition_key)
    if artifact_definition == ("lesson_division", "lesson.division.generate.output"):
        LessonDivisionRuntimeService(session, actor).open_approval(artifact_version_id)
    elif artifact_definition == ("lesson_plan", "lesson_plan.generate.output"):
        LessonPlanRuntimeService(session, actor).open_approval(artifact_version_id)
    elif artifact_definition == ("intro_option_set", "intro.generate_options.output"):
        IntroOptionRuntimeService(session, actor).open_approval(artifact_version_id)
