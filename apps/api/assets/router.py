"""Tenant-safe file asset and material parse metadata endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from apps.api.assets.models import FileAssetVersion, MaterialParseVersion
from apps.api.assets.repository import FileAssetRepository, MaterialFileRecord
from apps.api.assets.schemas import (
    FileAssetEnvelope,
    FileAssetRead,
    FileAssetVersionRead,
    MaterialParseVersionListData,
    MaterialParseVersionListEnvelope,
    MaterialParseVersionRead,
)
from apps.api.dependencies import get_session
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.dependencies import get_actor_context
from apps.api.identity.permissions import ProjectAccessService

router = APIRouter(tags=["assets"])


@router.get(
    "/api/v2/projects/{project_id}/materials/{material_id}/file-asset",
    response_model=FileAssetEnvelope,
    operation_id="getSourceMaterialFileAsset",
)
def get_source_material_file_asset(
    project_id: UUID,
    material_id: UUID,
    request: Request,
    response: Response,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> FileAssetEnvelope:
    ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    record = FileAssetRepository(session, actor).get_for_material(project_id, material_id)
    if record is None:
        raise material_file_not_found()
    response.headers["ETag"] = f'W/"{record.asset.lock_version}"'
    return FileAssetEnvelope(
        data=serialize_file_asset(record),
        request_id=request.state.request_id,
    )


@router.get(
    "/api/v2/projects/{project_id}/materials/{material_id}/parse-versions",
    response_model=MaterialParseVersionListEnvelope,
    operation_id="listMaterialParseVersions",
)
def list_material_parse_versions(
    project_id: UUID,
    material_id: UUID,
    request: Request,
    actor: Annotated[ActorContext, Depends(get_actor_context)],
    session: Annotated[Session, Depends(get_session)],
) -> MaterialParseVersionListEnvelope:
    ProjectAccessService(session, actor).require(project_id, ProjectAction.VIEW)
    repository = FileAssetRepository(session, actor)
    if repository.get_for_material(project_id, material_id) is None:
        raise material_file_not_found()
    parses = repository.list_parse_versions(project_id, material_id)
    return MaterialParseVersionListEnvelope(
        data=MaterialParseVersionListData(items=[serialize_parse(item) for item in parses]),
        request_id=request.state.request_id,
    )


def serialize_file_asset(record: MaterialFileRecord) -> FileAssetRead:
    return FileAssetRead.model_validate(
        {
            "id": record.asset.id,
            "asset_key": record.asset.asset_key,
            "asset_kind": record.asset.asset_kind,
            "status": record.asset.status,
            "retention_class": record.asset.retention_class,
            "lock_version": record.asset.lock_version,
            "current_version": serialize_file_version(record.current_version),
        }
    )


def serialize_file_version(version: FileAssetVersion) -> FileAssetVersionRead:
    return FileAssetVersionRead.model_validate(
        {
            "id": version.id,
            "version_no": version.version_no,
            "mime_type": version.mime_type,
            "byte_size": version.byte_size,
            "sha256": version.sha256,
            "width": version.width,
            "height": version.height,
            "duration_ms": version.duration_ms,
            "page_count": version.page_count,
            "scan_status": version.scan_status,
            "derived_from_version_id": version.derived_from_version_id,
            "created_at": version.created_at,
        }
    )


def serialize_parse(parse: MaterialParseVersion) -> MaterialParseVersionRead:
    return MaterialParseVersionRead.model_validate(
        {
            "id": parse.id,
            "source_material_id": parse.source_material_id,
            "file_asset_version_id": parse.file_asset_version_id,
            "version_no": parse.version_no,
            "status": parse.status,
            "parser_name": parse.parser_name,
            "parser_version": parse.parser_version,
            "page_count": parse.page_count,
            "text_checksum": parse.text_checksum,
            "validation_report": parse.validation_report_json,
            "error_code": parse.error_code,
            "created_at": parse.created_at,
            "started_at": parse.started_at,
            "completed_at": parse.completed_at,
        }
    )


def material_file_not_found() -> ApiError:
    return ApiError(
        status_code=404,
        code="MATERIAL_FILE_NOT_FOUND",
        message="The source material file was not found.",
    )
