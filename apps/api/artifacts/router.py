"""Artifact draft, version, and approval endpoints."""

from __future__ import annotations

import re
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from apps.api.artifacts.models import Approval, Artifact, ArtifactDraft, ArtifactVersion
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.schemas import (
    ApprovalEnvelope,
    ApprovalRead,
    ArtifactDraftEnvelope,
    ArtifactDraftRead,
    ArtifactEnvelope,
    ArtifactRead,
    ArtifactVersionEnvelope,
    ArtifactVersionRead,
    CreateArtifactRequest,
    ReviewArtifactVersionRequest,
    SaveArtifactDraftRequest,
    SubmitArtifactVersionRequest,
)
from apps.api.artifacts.service import ArtifactService
from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.identity.dependencies import get_actor_context
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.settings import Settings

router = APIRouter(tags=["artifacts"])
ETAG_PATTERN = re.compile(r'^(?:W/)?"(?P<version>[1-9][0-9]*)"$')


@router.post(
    "/api/v2/projects/{project_id}/artifacts",
    response_model=ArtifactEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="createArtifact",
)
def create_artifact(
    project_id: UUID,
    payload: CreateArtifactRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> ArtifactEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def command() -> CommandResult:
        artifact = ArtifactService(session, actor).create(
            project_id,
            artifact_key=payload.artifact_key,
            artifact_type=payload.artifact_type,
            branch_key=payload.branch_key,
            content_definition_version_id=payload.content_definition_version_id,
            lesson_unit_id=payload.lesson_unit_id,
            draft_branch=payload.draft_branch,
            initial_content=payload.content,
            request_id=request.state.request_id,
        )
        data = serialize_artifact(session, actor, artifact)
        return CommandResult(
            status_code=201,
            body=data.model_dump(mode="json"),
            resource_type="artifact",
            resource_id=artifact.id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"artifacts.create:{project_id}:{actor.principal_id}",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            command=command,
        )
    return ArtifactEnvelope(
        data=ArtifactRead.model_validate(result.body), request_id=request.state.request_id
    )


@router.get(
    "/api/v2/artifacts/{artifact_id}",
    response_model=ArtifactEnvelope,
    operation_id="getArtifact",
)
def get_artifact(
    artifact_id: UUID,
    request: Request,
    response: Response,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> ArtifactEnvelope:
    artifact = ArtifactRepository(session, actor).get(artifact_id)
    if artifact is None:
        raise artifact_not_found()
    data = serialize_artifact(session, actor, artifact)
    response.headers["ETag"] = weak_etag(
        data.current_draft.lock_version if data.current_draft is not None else data.lock_version
    )
    return ArtifactEnvelope(data=data, request_id=request.state.request_id)


@router.put(
    "/api/v2/artifacts/{artifact_id}/drafts/{draft_branch}",
    response_model=ArtifactDraftEnvelope,
    operation_id="saveArtifactDraft",
)
def save_artifact_draft(
    artifact_id: UUID,
    draft_branch: str,
    payload: SaveArtifactDraftRequest,
    request: Request,
    response: Response,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> ArtifactDraftEnvelope:
    expected_version = parse_etag(if_match)
    settings = cast(Settings, request.app.state.settings)
    request_payload = payload.model_dump(mode="json") | {"if_match": expected_version}

    def command() -> CommandResult:
        draft = ArtifactService(session, actor).save_draft(
            artifact_id,
            draft_branch,
            expected_lock_version=expected_version,
            content=payload.content,
            request_id=request.state.request_id,
        )
        data = serialize_draft(draft)
        return CommandResult(
            status_code=200,
            body=data.model_dump(mode="json"),
            resource_type="artifact_draft",
            resource_id=draft.id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"artifacts.draft.save:{artifact_id}:{draft_branch}:{actor.principal_id}",
            key=idempotency_key,
            payload=request_payload,
            command=command,
        )
    data = ArtifactDraftRead.model_validate(result.body)
    response.headers["ETag"] = weak_etag(data.lock_version)
    return ArtifactDraftEnvelope(data=data, request_id=request.state.request_id)


@router.post(
    "/api/v2/artifacts/{artifact_id}/versions",
    response_model=ArtifactVersionEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="submitArtifactVersion",
)
def submit_artifact_version(
    artifact_id: UUID,
    payload: SubmitArtifactVersionRequest,
    request: Request,
    if_match: Annotated[str, Header(alias="If-Match")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> ArtifactVersionEnvelope:
    expected_version = parse_etag(if_match)
    settings = cast(Settings, request.app.state.settings)
    request_payload = payload.model_dump(mode="json") | {"if_match": expected_version}

    def command() -> CommandResult:
        version = ArtifactService(session, actor).submit(
            artifact_id,
            payload.draft_branch,
            expected_lock_version=expected_version,
            source_kind="manual",
            request_id=request.state.request_id,
        )
        data = serialize_version(version)
        return CommandResult(
            status_code=201,
            body=data.model_dump(mode="json"),
            resource_type="artifact_version",
            resource_id=version.id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"artifacts.version.submit:{artifact_id}:{actor.principal_id}",
            key=idempotency_key,
            payload=request_payload,
            command=command,
        )
    return ArtifactVersionEnvelope(
        data=ArtifactVersionRead.model_validate(result.body),
        request_id=request.state.request_id,
    )


@router.post(
    "/api/v2/artifact-versions/{artifact_version_id}/approvals",
    response_model=ApprovalEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="reviewArtifactVersion",
)
def review_artifact_version(
    artifact_version_id: UUID,
    payload: ReviewArtifactVersionRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> ApprovalEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def command() -> CommandResult:
        approval = ArtifactService(session, actor).review(
            artifact_version_id,
            action=payload.action,
            comment=payload.comment,
            request_id=request.state.request_id,
        )
        data = serialize_approval(approval)
        return CommandResult(
            status_code=201,
            body=data.model_dump(mode="json"),
            resource_type="approval",
            resource_id=approval.id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"artifacts.review:{artifact_version_id}:{actor.principal_id}",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            command=command,
        )
    return ApprovalEnvelope(
        data=ApprovalRead.model_validate(result.body), request_id=request.state.request_id
    )


def serialize_artifact(
    session: Session,
    actor: ActorContext,
    artifact: Artifact,
) -> ArtifactRead:
    repository = ArtifactRepository(session, actor)
    current_draft = (
        session.get(ArtifactDraft, artifact.current_draft_id)
        if artifact.current_draft_id is not None
        else None
    )
    submitted = (
        repository.get_version(artifact.current_submitted_version_id)
        if artifact.current_submitted_version_id is not None
        else None
    )
    approved = (
        repository.get_version(artifact.current_approved_version_id)
        if artifact.current_approved_version_id is not None
        else None
    )
    return ArtifactRead.model_validate(
        {
            "id": artifact.id,
            "project_id": artifact.project_id,
            "lesson_unit_id": artifact.lesson_unit_id,
            "branch_key": artifact.branch_key,
            "artifact_key": artifact.artifact_key,
            "artifact_type": artifact.artifact_type,
            "content_definition_version_id": artifact.content_definition_version_id,
            "status": artifact.status,
            "stale_reason": artifact.stale_reason_json,
            "lock_version": artifact.lock_version,
            "current_draft": (
                serialize_draft(current_draft) if current_draft is not None else None
            ),
            "current_submitted_version": (
                serialize_version(submitted[0]) if submitted is not None else None
            ),
            "current_approved_version": (
                serialize_version(approved[0]) if approved is not None else None
            ),
            "created_at": artifact.created_at,
            "updated_at": artifact.updated_at,
        }
    )


def serialize_draft(draft: ArtifactDraft) -> ArtifactDraftRead:
    return ArtifactDraftRead(
        id=draft.id,
        draft_branch=draft.draft_branch,
        content=draft.content_json,
        validation_report=draft.validation_report_json,
        based_on_version_id=draft.based_on_version_id,
        autosaved_at=draft.autosaved_at,
        lock_version=draft.lock_version,
    )


def serialize_version(version: ArtifactVersion) -> ArtifactVersionRead:
    return ArtifactVersionRead.model_validate(
        {
            "id": version.id,
            "version_no": version.version_no,
            "content": version.content_json,
            "content_hash": version.content_hash,
            "render_summary": version.render_summary_json,
            "source_kind": version.source_kind,
            "source_node_run_id": version.source_node_run_id,
            "context_snapshot_id": version.context_snapshot_id,
            "prompt_snapshot_id": version.prompt_snapshot_id,
            "validation_report": version.validation_report_json,
            "created_at": version.created_at,
            "created_by": version.created_by,
        }
    )


def serialize_approval(approval: Approval) -> ApprovalRead:
    return ApprovalRead.model_validate(
        {
            "id": approval.id,
            "artifact_version_id": approval.artifact_version_id,
            "action": approval.action,
            "actor_type": approval.actor_type,
            "actor_user_id": approval.actor_user_id,
            "comment": approval.comment,
            "quality_evidence": approval.quality_evidence_json,
            "policy_snapshot": approval.policy_snapshot_json,
            "created_at": approval.created_at,
        }
    )


def parse_etag(value: str) -> int:
    match = ETAG_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="If-Match must contain a valid resource ETag.",
            details={"field": "If-Match"},
        )
    return int(match.group("version"))


def weak_etag(version: int) -> str:
    return f'W/"{version}"'


def artifact_not_found() -> ApiError:
    return ApiError(
        status_code=404,
        code="ARTIFACT_NOT_FOUND",
        message="The artifact resource was not found.",
    )
