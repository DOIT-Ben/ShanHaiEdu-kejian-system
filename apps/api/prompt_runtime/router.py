"""Privacy-safe prompt preview endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.identity.dependencies import get_actor_context
from apps.api.prompt_runtime.schemas import PromptPreviewEnvelope, PromptPreviewRead
from apps.api.prompt_runtime.service import PromptSnapshotError, PromptSnapshotService

router = APIRouter(tags=["prompt-runtime"])


@router.get(
    "/api/v2/node-runs/{node_run_id}/prompt-preview",
    response_model=PromptPreviewEnvelope,
    operation_id="getPromptPreview",
)
def get_prompt_preview(
    node_run_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> PromptPreviewEnvelope:
    try:
        snapshot = PromptSnapshotService(session, actor).get_prompt(node_run_id)
    except PromptSnapshotError as exc:
        raise ApiError(
            status_code=404,
            code=exc.code,
            message="The prompt preview was not found.",
        ) from exc
    data = PromptPreviewRead.model_validate(
        snapshot.preview_json
        | {
            "prompt_snapshot_id": snapshot.id,
            "content_hash": snapshot.content_hash,
        }
    )
    return PromptPreviewEnvelope(data=data, request_id=request.state.request_id)
