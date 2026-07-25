"""HTTP command for starting a prepared model-generation NodeRun."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, Request, status
from sqlalchemy.orm import Session

from apps.api.dependencies import get_session
from apps.api.identity.context import ActorContext
from apps.api.identity.dependencies import get_actor_context
from apps.api.jobs.schemas import AcceptedJobEnvelope
from apps.api.settings import Settings
from apps.api.workflows.schemas import StartNodeRunRequest
from apps.api.workflows.start_service import NodeRunStartService

router = APIRouter(tags=["workflows"])


@router.post(
    "/api/v2/node-runs/{node_run_id}/start",
    response_model=AcceptedJobEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="startNodeRun",
)
def start_node_run(
    node_run_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
    payload: Annotated[StartNodeRunRequest | None, Body()] = None,
) -> AcceptedJobEnvelope:
    settings = cast(Settings, request.app.state.settings)
    with session.begin():
        accepted = NodeRunStartService(
            session,
            actor,
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
        ).start(
            node_run_id,
            payload or StartNodeRunRequest(),
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return AcceptedJobEnvelope(data=accepted, request_id=request.state.request_id)
