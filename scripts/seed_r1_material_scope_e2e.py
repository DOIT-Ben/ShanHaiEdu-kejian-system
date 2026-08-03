#!/usr/bin/env python3
"""Seed material-scope, isolation, and reparse fixtures for real API browser gates."""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy.orm import Session

from apps.api.assets.models import FileAsset, FileAssetVersion, MaterialParseVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.context import ActorContext, AuthenticatedIdentity
from apps.api.identity.models import Principal
from apps.api.identity.repository import IdentityRepository
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.model_registry import register_models
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.settings import get_settings
from apps.api.uploads.models import SourceMaterial
from apps.api.uploads.storage import ObjectStorage, build_object_storage

PRIMARY_PROJECT_TITLE = "教材范围与课时划分验收"
ISOLATION_PROJECT_TITLE = "教材范围隔离验收"
REPARSE_PROJECT_TITLE = "教材重新解析验收"
E2E_TEXTBOOK_NAME = "shanhai-r1-e2e-textbook.pdf"
E2E_REPARSE_TEXTBOOK_NAME = "shanhai-r1-reparse-textbook.pdf"
PDF_PAGE_TEXTS = ("R1 evidence page 1", "R1 evidence page 2", "R1 evidence page 3")
ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_LOCATOR_ENV = "SHANHAI_R1_ACCEPTANCE_LOCATOR"


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _controlled_textbook_bytes() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)  # pyright: ignore[reportPrivateUsage]
    for text in PDF_PAGE_TEXTS:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
        )
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(  # pyright: ignore[reportPrivateUsage]
            content
        )
    writer.write(output)
    return output.getvalue()


def _write_controlled_textbook(payload: bytes) -> Path:
    destination = Path(tempfile.gettempdir()) / E2E_TEXTBOOK_NAME
    destination.write_bytes(payload)
    return destination


def _seed_failed_reparse_material(
    session: Session,
    actor: ActorContext,
    *,
    project_id: UUID,
    storage: ObjectStorage,
    payload: bytes,
) -> None:
    now = datetime.now(UTC)
    material_id = new_uuid7()
    asset_id = new_uuid7()
    version_id = new_uuid7()
    job_id = new_uuid7()
    storage_key = f"e2e/material-reparse/{project_id}/source.pdf"
    metadata = storage.put_bytes(
        bucket=get_settings().object_storage_bucket,
        key=storage_key,
        payload=payload,
        media_type="application/pdf",
    )
    asset = FileAsset(
        id=asset_id,
        organization_id=actor.organization_id,
        asset_key=f"material:{material_id}",
        asset_kind="source_material",
        current_version_id=None,
        status="active",
        retention_class="project_source",
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(asset)
    session.flush()
    version = FileAssetVersion(
        id=version_id,
        organization_id=actor.organization_id,
        file_asset_id=asset.id,
        version_no=1,
        storage_bucket=metadata.bucket,
        storage_key=metadata.key,
        mime_type="application/pdf",
        byte_size=metadata.size_bytes,
        sha256=metadata.sha256 or hashlib.sha256(payload).hexdigest(),
        etag=metadata.etag,
        page_count=None,
        scan_status="clean",
        metadata_json={},
        created_at=now,
        created_by=actor.principal_id,
    )
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    material = SourceMaterial(
        id=material_id,
        organization_id=actor.organization_id,
        project_id=project_id,
        material_kind="textbook",
        file_asset_id=asset.id,
        original_filename=E2E_REPARSE_TEXTBOOK_NAME,
        mime_type="application/pdf",
        upload_status="confirmed",
        confirmed_at=now,
        confirmed_by=actor.principal_id,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    job = GenerationJob(
        id=job_id,
        organization_id=actor.organization_id,
        project_id=project_id,
        source_material_id=material.id,
        creation_request_json={"file_asset_version_id": str(version.id)},
        job_type="material.parse",
        status="failed",
        progress_percent=45,
        progress_message="Material parsing failed",
        error_code="PDF_DAMAGED",
        idempotency_key="initial-material-parse",
        request_hash="b" * 64,
        priority=100,
        attempt_count=1,
        finished_at=now,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(material)
    session.flush()
    session.add(job)
    session.flush()
    session.add(
        MaterialParseVersion(
            id=new_uuid7(),
            organization_id=actor.organization_id,
            source_material_id=material.id,
            file_asset_version_id=version.id,
            generation_job_id=job.id,
            version_no=1,
            status="failed",
            parser_name="pypdf",
            parser_version="1.0",
            content_json=None,
            page_count=None,
            text_checksum=None,
            validation_report_json={"valid": False},
            error_code="PDF_DAMAGED",
            created_at=now,
            started_at=now,
            completed_at=now,
            created_by=actor.principal_id,
            updated_by=actor.principal_id,
        )
    )


def _extend_acceptance_locator(lesson_division_project_id: UUID) -> None:
    configured = os.environ.get(ACCEPTANCE_LOCATOR_ENV)
    if not configured:
        return
    destination = Path(configured)
    if not destination.is_absolute():
        raise RuntimeError(f"{ACCEPTANCE_LOCATOR_ENV} must be an absolute path")
    resolved = destination.resolve()
    if resolved.is_relative_to(ROOT):
        raise RuntimeError("the R1 acceptance locator must remain outside the repository")
    try:
        raw_payload: object = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("the R1 lesson acceptance locator must exist first") from error
    if not isinstance(raw_payload, dict):
        raise RuntimeError("the R1 lesson acceptance locator is incomplete")
    payload = cast(dict[str, object], raw_payload)
    if set(payload) != {
        "project_id",
        "lesson_unit_id",
        "isolation_lesson_unit_id",
    }:
        raise RuntimeError("the R1 lesson acceptance locator is incomplete")
    payload["lesson_division_project_id"] = str(lesson_division_project_id)
    resolved.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> int:
    register_models()
    payload = _controlled_textbook_bytes()
    storage = build_object_storage(get_settings())
    if storage is None:
        raise RuntimeError("the R1 material seed requires object storage")
    engine = build_engine(_required("SHANHAI_DATABASE_URL"))
    factory = build_session_factory(engine)
    try:
        with factory() as session, session.begin():
            principal = session.get(
                Principal,
                UUID(_required("SHANHAI_SESSION_TEACHER_PRINCIPAL_ID")),
            )
            if principal is None or principal.user_id is None:
                raise RuntimeError("the controlled E2E teacher principal is unavailable")
            actor = IdentityRepository(session).resolve_actor(
                AuthenticatedIdentity(
                    user_id=principal.user_id,
                    organization_id=principal.organization_id,
                )
            )
            ContentReleasePublisher(session).publish(
                load_builtin_courseware_release(ROOT),
                published_by=actor.principal_id,
            )
            lesson_division_project_id: UUID | None = None
            for title in (PRIMARY_PROJECT_TITLE, ISOLATION_PROJECT_TITLE, REPARSE_PROJECT_TITLE):
                project = ProjectRepository(session, actor).create(
                    CreateProjectRequest(
                        grade="一年级",
                        knowledge_point="1-5的认识",
                        textbook_edition="人教版",
                        title=title,
                    )
                )
                if title == PRIMARY_PROJECT_TITLE:
                    lesson_division_project_id = project.id
                elif title == REPARSE_PROJECT_TITLE:
                    _seed_failed_reparse_material(
                        session,
                        actor,
                        project_id=project.id,
                        storage=storage,
                        payload=payload,
                    )
        if lesson_division_project_id is None:
            raise RuntimeError("the R1 lesson-division project was not created")
        _extend_acceptance_locator(lesson_division_project_id)
        textbook = _write_controlled_textbook(payload)
        print(f"r1 material scope projects and controlled PDF seeded: {textbook}", flush=True)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
