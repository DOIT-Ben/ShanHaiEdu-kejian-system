"""Material parse version application service used by API and workers."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.assets.domain import ParseInvariantError, ParseStatus, ensure_parse_transition
from apps.api.assets.models import MaterialParseVersion
from apps.api.assets.repository import FileAssetRepository
from apps.api.database import utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import ActorContext, ProjectAction
from apps.api.identity.permissions import ProjectAccessService
from apps.api.ids import new_uuid7
from apps.api.uploads.models import SourceMaterial

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class MaterialParseService:
    def __init__(self, session: Session, actor: ActorContext) -> None:
        self._session = session
        self._actor = actor
        self._repository = FileAssetRepository(session, actor)

    def create(
        self,
        source_material_id: UUID,
        file_asset_version_id: UUID,
        *,
        parser_name: str,
        parser_version: str,
    ) -> MaterialParseVersion:
        if not parser_name.strip() or len(parser_name) > 120:
            raise self._invalid_output("The parser name is invalid.")
        if not parser_version.strip() or len(parser_version) > 80:
            raise self._invalid_output("The parser version is invalid.")
        material = self._require_material(source_material_id, ProjectAction.GENERATE)
        if material.file_asset_id is None or material.upload_status != "confirmed":
            raise self._invalid_source("The source material has no confirmed file asset.")
        version = self._repository.get_file_version(file_asset_version_id)
        if version is None or version.file_asset_id != material.file_asset_id:
            raise self._invalid_source("The file version does not belong to the source material.")
        parse = MaterialParseVersion(
            id=new_uuid7(),
            organization_id=self._actor.organization_id,
            source_material_id=material.id,
            file_asset_version_id=version.id,
            version_no=self._repository.next_parse_version_no(material.id),
            status=ParseStatus.PENDING.value,
            parser_name=parser_name,
            parser_version=parser_version,
            content_json=None,
            page_count=None,
            text_checksum=None,
            validation_report_json={},
            error_code=None,
            created_at=utc_now(),
            created_by=self._actor.principal_id,
            updated_by=self._actor.principal_id,
        )
        self._session.add(parse)
        self._session.flush()
        return parse

    def start(self, parse_id: UUID) -> MaterialParseVersion:
        parse = self._require_parse(parse_id)
        self._transition(parse, ParseStatus.RUNNING)
        parse.started_at = utc_now()
        parse.updated_by = self._actor.principal_id
        self._session.flush()
        return parse

    def complete(
        self,
        parse_id: UUID,
        *,
        content: dict[str, Any],
        page_count: int,
        text_checksum: str,
        validation_report: dict[str, Any],
    ) -> MaterialParseVersion:
        if page_count <= 0:
            raise self._invalid_output("The parse page count must be greater than zero.")
        if SHA256_PATTERN.fullmatch(text_checksum) is None:
            raise self._invalid_output("The parse text checksum must be a SHA-256 value.")
        parse = self._require_parse(parse_id)
        self._transition(parse, ParseStatus.SUCCEEDED)
        parse.content_json = content
        parse.page_count = page_count
        parse.text_checksum = text_checksum
        parse.validation_report_json = validation_report
        parse.error_code = None
        parse.completed_at = utc_now()
        parse.updated_by = self._actor.principal_id
        file_version = self._repository.get_file_version(parse.file_asset_version_id)
        if file_version is None:
            raise self._invalid_source("The parsed file version is unavailable.")
        if file_version.page_count is not None and file_version.page_count != page_count:
            raise ApiError(
                status_code=409,
                code="FILE_METADATA_CONFLICT",
                message="The parsed page count conflicts with immutable file metadata.",
            )
        file_version.page_count = page_count
        self._session.flush()
        return parse

    def fail(
        self,
        parse_id: UUID,
        *,
        error_code: str,
        validation_report: dict[str, Any],
    ) -> MaterialParseVersion:
        if not error_code.strip() or len(error_code) > 120:
            raise self._invalid_output("The parse error code is invalid.")
        parse = self._require_parse(parse_id)
        self._transition(parse, ParseStatus.FAILED)
        parse.error_code = error_code
        parse.validation_report_json = validation_report
        parse.completed_at = utc_now()
        parse.updated_by = self._actor.principal_id
        self._session.flush()
        return parse

    def _require_material(
        self,
        material_id: UUID,
        action: ProjectAction,
    ) -> SourceMaterial:
        visible = self._repository.get_material(material_id)
        if visible is None:
            raise self._not_found()
        if not self._actor.is_system:
            ProjectAccessService(self._session, self._actor).require(
                visible.project_id,
                action,
                for_update=True,
            )
        locked = self._repository.lock_material(material_id)
        if locked is None:
            raise self._not_found()
        return locked

    def _require_parse(self, parse_id: UUID) -> MaterialParseVersion:
        visible = self._repository.get_parse(parse_id)
        if visible is None:
            raise self._not_found()
        self._require_material(visible.source_material_id, ProjectAction.GENERATE)
        locked = self._repository.get_parse(parse_id, for_update=True)
        if locked is None:
            raise self._not_found()
        return locked

    @staticmethod
    def _transition(parse: MaterialParseVersion, target: ParseStatus) -> None:
        try:
            ensure_parse_transition(ParseStatus(parse.status), target)
        except ParseInvariantError as exc:
            raise ApiError(
                status_code=409,
                code="PARSE_VERSION_IMMUTABLE",
                message="The material parse version cannot make this transition.",
            ) from exc
        parse.status = target.value

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(
            status_code=404,
            code="MATERIAL_PARSE_NOT_FOUND",
            message="The material parse resource was not found.",
        )

    @staticmethod
    def _invalid_source(message: str) -> ApiError:
        return ApiError(status_code=422, code="INVALID_PARSE_SOURCE", message=message)

    @staticmethod
    def _invalid_output(message: str) -> ApiError:
        return ApiError(status_code=422, code="INVALID_PARSE_OUTPUT", message=message)
