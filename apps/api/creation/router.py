"""Creation lifecycle HTTP endpoints."""

from __future__ import annotations

import hashlib
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from apps.api.creation.repository import CreationRepository
from apps.api.creation.schemas import (
    AdoptGenerationResultRequest,
    AdoptionEnvelope,
    CreateCreationBatchRequest,
    CreationBatchEnvelope,
    GenerateCreationBatchRequest,
    GenerateCreationItemRequest,
    LegacyGenerateCreationBatchRequest,
    LegacySaveGenerationResultRequest,
    ProjectSourceSaveRequest,
    PromptVersionEnvelope,
    SaveAdoptionToProjectRequest,
    SavePromptVersionRequest,
    SaveToProjectOperationEnvelope,
    StandaloneSourceSaveRequest,
)
from apps.api.creation.service import CreationService
from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.identity.dependencies import get_actor_context
from apps.api.jobs.schemas import AcceptedJobEnvelope
from apps.api.settings import Settings

router = APIRouter(prefix="/api/v2", tags=["creation"])
IdempotencyHeader = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=128),
]


def _legacy_child_idempotency_key(parent: str, action: str) -> str:
    digest = hashlib.sha256(parent.encode("utf-8")).hexdigest()
    return f"legacy:{action}:{digest}"


def service(request: Request, session: Session, actor: ActorContext) -> CreationService:
    settings = cast(Settings, request.app.state.settings)
    return CreationService(
        session,
        actor,
        idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
    )


@router.post(
    "/creation-batches",
    response_model=CreationBatchEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="createCreationBatch",
)
def create_creation_batch(
    payload: CreateCreationBatchRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> CreationBatchEnvelope:
    with session.begin():
        data = service(request, session, actor).create_batch(
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return CreationBatchEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/creation-batches/{batch_id}/generate",
    response_model=AcceptedJobEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="generateCreationBatch",
)
def generate_creation_batch(
    batch_id: UUID,
    payload: GenerateCreationBatchRequest | LegacyGenerateCreationBatchRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AcceptedJobEnvelope:
    with session.begin():
        data = service(request, session, actor).generate_batch(
            batch_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return AcceptedJobEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/creation-items/{item_id}/prompt-versions",
    response_model=PromptVersionEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="saveCreationPromptVersion",
)
def save_creation_prompt_version(
    item_id: UUID,
    payload: SavePromptVersionRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> PromptVersionEnvelope:
    with session.begin():
        data = service(request, session, actor).save_prompt_version(
            item_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return PromptVersionEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/creation-items/{item_id}/generate",
    response_model=AcceptedJobEnvelope,
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="generateCreationItem",
)
def generate_creation_item(
    item_id: UUID,
    payload: GenerateCreationItemRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AcceptedJobEnvelope:
    with session.begin():
        data = service(request, session, actor).generate_item(
            item_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return AcceptedJobEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/generation-results/{result_id}/adoptions",
    response_model=AdoptionEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="adoptGenerationResult",
)
def adopt_generation_result(
    result_id: UUID,
    payload: AdoptGenerationResultRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AdoptionEnvelope:
    with session.begin():
        data = service(request, session, actor).adopt_result(
            result_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return AdoptionEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/adoptions/{adoption_id}/save-to-project",
    response_model=SaveToProjectOperationEnvelope,
    operation_id="saveAdoptionToProject",
)
def save_adoption_to_project(
    adoption_id: UUID,
    payload: SaveAdoptionToProjectRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> SaveToProjectOperationEnvelope:
    with session.begin():
        data = service(request, session, actor).save_adoption(
            adoption_id,
            payload,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    return SaveToProjectOperationEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/generation-results/{result_id}/save-to-project",
    response_model=SaveToProjectOperationEnvelope,
    deprecated=True,
    operation_id="saveGenerationResultToProject",
)
def legacy_save_generation_result(
    result_id: UUID,
    payload: LegacySaveGenerationResultRequest,
    request: Request,
    idempotency_key: IdempotencyHeader,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> SaveToProjectOperationEnvelope:
    creation = service(request, session, actor)
    with session.begin():
        context = CreationRepository(session, actor.organization_id).get_result_context(result_id)
        if context is None:
            raise ApiError(
                status_code=404,
                code="GENERATION_RESULT_NOT_FOUND",
                message="The generation result was not found.",
            )
        adoption = creation.adopt_result(
            result_id,
            AdoptGenerationResultRequest(reason="legacy direct-save adapter"),
            idempotency_key=_legacy_child_idempotency_key(idempotency_key, "adopt"),
            request_id=request.state.request_id,
        )
        if context.batch.source_kind == "project":
            if (
                context.batch.source_project_id != payload.project_id
                or context.item.target_slot_key != payload.slot_key
            ):
                raise ApiError(
                    status_code=422,
                    code="TARGET_OVERRIDE_FORBIDDEN",
                    message="The legacy request cannot override the package target.",
                )
            save_payload = ProjectSourceSaveRequest(
                source_kind="project",
                replace_mode=payload.replace_mode,
            )
        else:
            save_payload = StandaloneSourceSaveRequest(
                source_kind="standalone",
                project_id=payload.project_id,
                slot_key=payload.slot_key,
                replace_mode=payload.replace_mode,
            )
        data = creation.save_adoption(
            adoption.id,
            save_payload,
            idempotency_key=_legacy_child_idempotency_key(idempotency_key, "save"),
            request_id=request.state.request_id,
        )
    return SaveToProjectOperationEnvelope(data=data, request_id=request.state.request_id)
