"""HTTP command for project material-scope immutable versions."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from apps.api.artifacts.material_scope_service import MaterialScopeVersionService
from apps.api.artifacts.router import serialize_artifact
from apps.api.artifacts.schemas import (
    ArtifactEnvelope,
    ArtifactRead,
    CreateMaterialScopeVersionRequest,
)
from apps.api.dependencies import get_session
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.settings import Settings

router = APIRouter(tags=["artifacts"])


@router.post(
    "/api/v2/projects/{project_id}/material-scope/versions",
    response_model=ArtifactEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="createMaterialScopeVersion",
)
def create_material_scope_version(
    project_id: UUID,
    payload: CreateMaterialScopeVersionRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> ArtifactEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def command() -> CommandResult:
        artifact = MaterialScopeVersionService(session, actor).create(
            project_id,
            payload,
            request_id=request.state.request_id,
        )
        data = serialize_artifact(session, actor, artifact)
        return CommandResult(
            status_code=201,
            body=data.model_dump(mode="json"),
            resource_type="artifact_version",
            resource_id=artifact.current_submitted_version_id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"material-scope.version.create:{project_id}:{actor.principal_id}",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            authorize=lambda: ProjectAccessService(session, actor).require(
                project_id,
                ProjectAction.EDIT,
                for_update=True,
            ),
            command=command,
        )
    return ArtifactEnvelope(
        data=ArtifactRead.model_validate(result.body),
        request_id=request.state.request_id,
    )
