"""Prepare one exact LessonUnit Intro option generation NodeRun."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.intro_options.runtime import IntroOptionRuntimeService
from apps.api.intro_options.schemas import PrepareIntroOptionGenerationRequest
from apps.api.lessons.repository import LessonRepository
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.workflows.schemas import NodeRunRead


class IntroOptionGenerationPreparationService:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        idempotency_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._actor = actor
        self._idempotency = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=idempotency_ttl_seconds,
        )

    def prepare(
        self,
        lesson_id: UUID,
        payload: PrepareIntroOptionGenerationRequest,
        *,
        idempotency_key: str,
    ) -> NodeRunRead:
        def authorize():
            lesson = LessonRepository(self._session, self._actor).get(
                lesson_id,
                for_update=True,
            )
            if lesson is None or lesson.status != "active":
                raise ApiError(
                    status_code=404,
                    code="LESSON_NOT_FOUND",
                    message="The lesson was not found.",
                )
            ProjectAccessService(self._session, self._actor).require(
                lesson.project_id,
                ProjectAction.GENERATE,
                for_update=True,
            )
            return lesson

        def command() -> CommandResult:
            lesson = authorize()
            runtime = IntroOptionRuntimeService(self._session, self._actor)
            node_id = runtime.stage_generation(
                project_id=lesson.project_id,
                lesson_unit_id=lesson.id,
                generation_mode=payload.generation_mode,
                source_artifact_version_id=payload.source_artifact_version_id,
            )
            node = runtime.read_node(node_id)
            return CommandResult(
                status_code=200,
                body=node.model_dump(mode="json"),
                resource_type="node_run",
                resource_id=node.id,
            )

        result = self._idempotency.execute(
            scope=f"intro-options.prepare:{lesson_id}:{self._actor.principal_id}",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            authorize=authorize,
            command=command,
        )
        return NodeRunRead.model_validate(result.body)
