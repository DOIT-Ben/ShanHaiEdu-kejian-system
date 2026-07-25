"""Stage exact Intro option Artifact quality validation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.repository import ArtifactRepository
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.intro_options.runtime import IntroOptionRuntimeService
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.workflows.schemas import AcceptedNodeRunData
from workflow.node_state import NodeStatus


class IntroOptionQualityValidationService:
    def __init__(
        self,
        session: Session,
        actor: ActorContext,
        *,
        idempotency_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._actor = actor
        self._artifacts = ArtifactRepository(session, actor)
        self._idempotency = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=idempotency_ttl_seconds,
        )

    def start(
        self,
        lesson_unit_id: UUID,
        artifact_version_id: UUID,
        *,
        idempotency_key: str,
    ) -> AcceptedNodeRunData:
        def require_artifact(*, for_update: bool):
            record = self._artifacts.get_version(
                artifact_version_id,
                for_update_artifact=for_update,
            )
            if record is None:
                raise self._not_found()
            _version, artifact = record
            ProjectAccessService(self._session, self._actor).require(
                artifact.project_id,
                ProjectAction.GENERATE,
                for_update=for_update,
            )
            if (
                artifact.artifact_type != "intro_option_set"
                or artifact.branch_key != "intro_options"
                or artifact.lesson_unit_id != lesson_unit_id
            ):
                raise self._not_found()
            return artifact

        def command() -> CommandResult:
            artifact = require_artifact(for_update=True)
            runtime = IntroOptionRuntimeService(self._session, self._actor)
            node_id = runtime.stage_quality(artifact_version_id)
            node = runtime.read_node(node_id)
            data = AcceptedNodeRunData(
                node_run_id=node.id,
                status=NodeStatus(node.status),
                events_url=f"/api/v2/projects/{artifact.project_id}/events/stream",
            )
            return CommandResult(
                status_code=202,
                body=data.model_dump(mode="json"),
                resource_type="node_run",
                resource_id=node.id,
            )

        result = self._idempotency.execute(
            scope=f"intro-options.quality:{artifact_version_id}:{self._actor.principal_id}",
            key=idempotency_key,
            payload={},
            authorize=lambda: require_artifact(for_update=True),
            command=command,
        )
        return AcceptedNodeRunData.model_validate(result.body)

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="INTRO_OPTION_VERSION_NOT_FOUND",
            message="The Intro option ArtifactVersion was not found for this lesson.",
        )
