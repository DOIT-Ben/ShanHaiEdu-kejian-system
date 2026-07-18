"""Authorized project asset aggregation and atomic binding endpoints."""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from apps.api.assets.project_contracts import AssetCardinality, AssetTargetContract
from apps.api.assets.project_repository import ProjectAssetSlotView
from apps.api.assets.project_schemas import (
    AssetBindingEnvelope,
    AssetBindingRead,
    AssetPageMeta,
    BindAssetRequest,
    ProjectAssetPackageData,
    ProjectAssetPackageEnvelope,
    ProjectAssetSlotListData,
    ProjectAssetSlotListEnvelope,
    ProjectAssetSlotRead,
)
from apps.api.assets.project_service import ProjectAssetService
from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext
from apps.api.identity.dependencies import get_actor_context
from apps.api.reliability.idempotency import CommandResult, IdempotencyService
from apps.api.settings import Settings

router = APIRouter(tags=["project-assets"])


@router.get(
    "/api/v2/projects/{project_id}/asset-slots",
    response_model=ProjectAssetSlotListEnvelope,
    operation_id="listProjectAssetSlots",
)
def list_project_asset_slots(
    project_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
    lesson_unit_id: Annotated[UUID | None, Query()] = None,
    slot_key: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    page_cursor: Annotated[str | None, Query(alias="page[cursor]")] = None,
    page_limit: Annotated[int, Query(alias="page[limit]", ge=1, le=100)] = 20,
) -> ProjectAssetSlotListEnvelope:
    views, next_cursor = _list_views(
        session,
        actor,
        project_id,
        lesson_unit_id=lesson_unit_id,
        slot_key=slot_key,
        page_cursor=page_cursor,
        page_limit=page_limit,
    )
    return ProjectAssetSlotListEnvelope(
        data=ProjectAssetSlotListData(items=[_slot_read(view) for view in views]),
        meta=AssetPageMeta(next_cursor=next_cursor),
        request_id=request.state.request_id,
    )


@router.get(
    "/api/v2/projects/{project_id}/asset-package",
    response_model=ProjectAssetPackageEnvelope,
    operation_id="getProjectAssetPackage",
)
def get_project_asset_package(
    project_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
    lesson_unit_id: Annotated[UUID | None, Query()] = None,
    slot_key: Annotated[str | None, Query(min_length=1, max_length=160)] = None,
    page_cursor: Annotated[str | None, Query(alias="page[cursor]")] = None,
    page_limit: Annotated[int, Query(alias="page[limit]", ge=1, le=100)] = 20,
) -> ProjectAssetPackageEnvelope:
    views, next_cursor = _list_views(
        session,
        actor,
        project_id,
        lesson_unit_id=lesson_unit_id,
        slot_key=slot_key,
        page_cursor=page_cursor,
        page_limit=page_limit,
    )
    return ProjectAssetPackageEnvelope(
        data=ProjectAssetPackageData(
            project_id=project_id,
            items=[_slot_read(view) for view in views],
        ),
        meta=AssetPageMeta(next_cursor=next_cursor),
        request_id=request.state.request_id,
    )


@router.post(
    "/api/v2/asset-slots/{slot_id}/bindings",
    response_model=AssetBindingEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="bindProjectAsset",
)
def bind_project_asset(
    slot_id: UUID,
    payload: BindAssetRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AssetBindingEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def command() -> CommandResult:
        binding = ProjectAssetService(session, actor).bind(
            slot_id,
            file_asset_version_id=payload.file_asset_version_id,
            source_artifact_version_id=payload.source_artifact_version_id,
            replace_mode=payload.replace_mode,
            position=payload.position,
            request_id=request.state.request_id,
        )
        body = AssetBindingRead.model_validate(binding).model_dump(mode="json")
        return CommandResult(
            status_code=201,
            body=body,
            resource_type="asset_binding",
            resource_id=binding.id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"project_assets.bind:{slot_id}:{actor.principal_id}",
            key=idempotency_key,
            payload=payload.model_dump(mode="json"),
            authorize=lambda: ProjectAssetService(session, actor).require_slot_access(slot_id),
            command=command,
        )
    return AssetBindingEnvelope(
        data=AssetBindingRead.model_validate(result.body),
        request_id=request.state.request_id,
    )


@router.post(
    "/api/v2/asset-bindings/{binding_id}/unbind",
    response_model=AssetBindingEnvelope,
    operation_id="unbindProjectAsset",
)
def unbind_project_asset(
    binding_id: UUID,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> AssetBindingEnvelope:
    settings = cast(Settings, request.app.state.settings)

    def command() -> CommandResult:
        binding = ProjectAssetService(session, actor).unbind(
            binding_id,
            request_id=request.state.request_id,
        )
        body = AssetBindingRead.model_validate(binding).model_dump(mode="json")
        return CommandResult(
            status_code=200,
            body=body,
            resource_type="asset_binding",
            resource_id=binding.id,
        )

    with session.begin():
        result = IdempotencyService(
            session,
            actor.organization_id,
            ttl_seconds=settings.idempotency_ttl_seconds,
        ).execute(
            scope=f"project_assets.unbind:{binding_id}:{actor.principal_id}",
            key=idempotency_key,
            payload={"binding_id": str(binding_id)},
            authorize=lambda: ProjectAssetService(session, actor).require_binding_access(
                binding_id
            ),
            command=command,
        )
    return AssetBindingEnvelope(
        data=AssetBindingRead.model_validate(result.body),
        request_id=request.state.request_id,
    )


def _list_views(
    session: Session,
    actor: ActorContext,
    project_id: UUID,
    *,
    lesson_unit_id: UUID | None,
    slot_key: str | None,
    page_cursor: str | None,
    page_limit: int,
) -> tuple[list[ProjectAssetSlotView], str | None]:
    try:
        cursor = UUID(page_cursor) if page_cursor else None
    except ValueError as exc:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="The page cursor is invalid.",
            details={"field": "page[cursor]"},
        ) from exc
    return ProjectAssetService(session, actor).list_slots(
        project_id,
        cursor=cursor,
        limit=page_limit,
        lesson_unit_id=lesson_unit_id,
        slot_key=slot_key,
    )


def _slot_read(view: ProjectAssetSlotView) -> ProjectAssetSlotRead:
    slot = view.slot
    return ProjectAssetSlotRead(
        id=slot.id,
        project_id=slot.project_id,
        lesson_unit_id=slot.lesson_unit_id,
        slot_key=slot.slot_key,
        asset_type=slot.asset_type,
        cardinality=AssetCardinality(slot.cardinality),
        required=slot.required,
        status=cast(Literal["empty", "satisfied"], slot.status),
        target_contract=AssetTargetContract.model_validate(slot.target_contract_json),
        active_bindings=[
            AssetBindingRead.model_validate(binding) for binding in view.active_bindings
        ],
    )
