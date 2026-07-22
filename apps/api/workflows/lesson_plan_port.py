"""Compatibility wrapper over the shared lesson Artifact workflow staging port."""

from __future__ import annotations

from sqlalchemy.orm import Session

from apps.api.identity.context import ActorContext
from apps.api.workflows.artifact_port import (
    ArtifactInputSnapshot,
    ArtifactRunScope,
    ArtifactWorkflowPort,
)

LessonPlanInputSnapshot = ArtifactInputSnapshot
LessonPlanRunScope = ArtifactRunScope


class LessonPlanWorkflowPort(ArtifactWorkflowPort):
    def __init__(self, session: Session, actor: ActorContext) -> None:
        super().__init__(session, actor, error_code="LESSON_PLAN_RUNTIME_INVALID")
