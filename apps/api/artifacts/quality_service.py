"""Transactional dispatch for Artifact quality validation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.artifacts.models import Artifact
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.intro_options.runtime import IntroOptionRuntimeService
from apps.api.lessons.lesson_plan_runtime import LessonPlanRuntimeService
from apps.api.lessons.runtime_service import LessonDivisionRuntimeService
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.workflows.models import NodeRun, WorkflowRun
from apps.api.workflows.schemas import AcceptedNodeRunData


class ArtifactQualityValidationService:
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
        artifact_version_id: UUID,
        *,
        idempotency_key: str,
    ) -> AcceptedNodeRunData:
        def command() -> CommandResult:
            artifact = self._require_supported(artifact_version_id, for_update=True)
            node_id = self._stage(artifact, artifact_version_id)
            node = self._session.get(NodeRun, node_id)
            run = self._session.get(WorkflowRun, node.workflow_run_id) if node is not None else None
            if node is None or run is None or run.project_id != artifact.project_id:
                raise ApiError(
                    status_code=409,
                    code="ARTIFACT_QUALITY_RUNTIME_INVALID",
                    message="The exact quality validation NodeRun is unavailable.",
                )
            data = AcceptedNodeRunData(
                node_run_id=node.id,
                status=node.status,
                events_url=f"/api/v2/projects/{artifact.project_id}/events/stream",
            )
            return CommandResult(
                status_code=202,
                body=data.model_dump(mode="json"),
                resource_type="node_run",
                resource_id=node.id,
            )

        result = self._idempotency.execute(
            scope=(
                "artifact-versions.quality-validation:"
                f"{artifact_version_id}:{self._actor.principal_id}"
            ),
            key=idempotency_key,
            payload={},
            authorize=lambda: self._require_supported(
                artifact_version_id,
                for_update=True,
            ),
            command=command,
        )
        return AcceptedNodeRunData.model_validate(result.body)

    def _require_supported(
        self,
        artifact_version_id: UUID,
        *,
        for_update: bool,
    ) -> Artifact:
        record = self._artifacts.get_version(
            artifact_version_id,
            for_update_artifact=for_update,
        )
        if record is None:
            raise ApiError(
                status_code=404,
                code="ARTIFACT_NOT_FOUND",
                message="The artifact resource was not found.",
            )
        _version, artifact = record
        ProjectAccessService(self._session, self._actor).require(
            artifact.project_id,
            ProjectAction.GENERATE,
            for_update=for_update,
        )
        if artifact.artifact_type not in {
            "lesson_division",
            "lesson_plan",
            "intro_option_set",
        }:
            raise ApiError(
                status_code=409,
                code="ARTIFACT_QUALITY_UNSUPPORTED",
                message="The artifact type does not use quality validation.",
            )
        return artifact

    def _stage(self, artifact: Artifact, artifact_version_id: UUID) -> UUID:
        if artifact.artifact_type == "lesson_division":
            return LessonDivisionRuntimeService(self._session, self._actor).stage_quality(
                artifact_version_id
            )
        if artifact.artifact_type == "lesson_plan":
            return LessonPlanRuntimeService(self._session, self._actor).stage_quality(
                artifact_version_id
            )
        return IntroOptionRuntimeService(self._session, self._actor).stage_quality(
            artifact_version_id
        )
