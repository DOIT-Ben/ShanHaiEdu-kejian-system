"""Generation job fact query endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID
from apps.api.jobs.repository import GenerationJobRepository
from apps.api.jobs.schemas import GenerationJobEnvelope, GenerationJobRead

router = APIRouter(prefix="/api/v2/generation-jobs", tags=["generation-jobs"])


@router.get("/{job_id}", response_model=GenerationJobEnvelope, operation_id="getGenerationJob")
def get_generation_job(
    job_id: UUID,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> GenerationJobEnvelope:
    job = GenerationJobRepository(session, SYSTEM_ORGANIZATION_ID).get(job_id)
    if job is None:
        raise ApiError(
            status_code=404,
            code="GENERATION_JOB_NOT_FOUND",
            message="The generation job was not found.",
        )
    return GenerationJobEnvelope(
        data=GenerationJobRead.model_validate(job),
        request_id=request.state.request_id,
    )
