from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from apps.api.assets.models import FileAsset, FileAssetVersion, MaterialParseVersion
from apps.api.identity.context import ActorContext
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.uploads.models import SourceMaterial
from tests.fakes.identity import seed_test_actor


@dataclass(frozen=True, slots=True)
class SeededMaterialParse:
    actor: ActorContext
    project_id: UUID
    material_id: UUID
    file_asset_id: UUID
    file_asset_version_id: UUID
    generation_job_id: UUID
    parse_version_id: UUID


def seed_material_parse(
    factory: sessionmaker[Session],
    *,
    actor: ActorContext | None = None,
    parse_status: Literal["failed", "succeeded"] = "failed",
    title: str = "Material parse recovery",
) -> SeededMaterialParse:
    with factory() as session, session.begin():
        resolved_actor = actor or seed_test_actor(session)
        return seed_material_parse_in_session(
            session,
            resolved_actor,
            parse_status=parse_status,
            title=title,
        )


def seed_foreign_material_parse(
    factory: sessionmaker[Session],
) -> SeededMaterialParse:
    with factory() as session, session.begin():
        organization_id = new_uuid7()
        session.add(
            Organization(
                id=organization_id,
                slug=f"reparse-foreign-{organization_id.hex[-10:]}",
                name="Foreign reparse organization",
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        actor = seed_test_actor(
            session,
            organization_id=organization_id,
            user_id=new_uuid7(),
            principal_id=new_uuid7(),
            member_id=new_uuid7(),
            email=f"foreign-{organization_id.hex[-10:]}@example.test",
            display_name="Foreign teacher",
        )
        return seed_material_parse_in_session(
            session,
            actor,
            title="Foreign material parse",
        )


def seed_material_parse_in_session(
    session: Session,
    actor: ActorContext,
    *,
    parse_status: Literal["failed", "succeeded"] = "failed",
    title: str,
) -> SeededMaterialParse:
    now = datetime.now(UTC)
    project = ProjectRepository(session, actor).create(
        CreateProjectRequest(title=title, knowledge_point="One half")
    )
    material_id = new_uuid7()
    asset_id = new_uuid7()
    version_id = new_uuid7()
    job_id = new_uuid7()
    parse_id = new_uuid7()

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
        storage_bucket="shanhaiedu",
        storage_key=f"test/materials/{material_id}/source.pdf",
        mime_type="application/pdf",
        byte_size=128,
        sha256="a" * 64,
        etag="reparse-etag",
        page_count=1 if parse_status == "succeeded" else None,
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
        project_id=project.id,
        material_kind="textbook",
        file_asset_id=asset.id,
        original_filename="source.pdf",
        mime_type="application/pdf",
        upload_status="confirmed",
        confirmed_at=now,
        confirmed_by=actor.principal_id,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(material)
    session.flush()

    succeeded = parse_status == "succeeded"
    job = GenerationJob(
        id=job_id,
        organization_id=actor.organization_id,
        project_id=project.id,
        source_material_id=material.id,
        creation_request_json={"file_asset_version_id": str(version.id)},
        job_type="material.parse",
        status=parse_status,
        progress_percent=100 if succeeded else 45,
        progress_message="Material parsed" if succeeded else "Material parsing failed",
        error_code=None if succeeded else "PDF_DAMAGED",
        idempotency_key="initial-material-parse",
        request_hash="b" * 64,
        priority=100,
        attempt_count=1,
        finished_at=now,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(job)
    session.flush()
    parse = MaterialParseVersion(
        id=parse_id,
        organization_id=actor.organization_id,
        source_material_id=material.id,
        file_asset_version_id=version.id,
        generation_job_id=job.id,
        version_no=1,
        status=parse_status,
        parser_name="pypdf",
        parser_version="1.0",
        content_json={"pages": []} if succeeded else None,
        page_count=1 if succeeded else None,
        text_checksum="c" * 64 if succeeded else None,
        validation_report_json={"valid": succeeded},
        error_code=None if succeeded else "PDF_DAMAGED",
        created_at=now,
        started_at=now,
        completed_at=now,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(parse)
    session.flush()
    return SeededMaterialParse(
        actor=actor,
        project_id=project.id,
        material_id=material.id,
        file_asset_id=asset.id,
        file_asset_version_id=version.id,
        generation_job_id=job.id,
        parse_version_id=parse.id,
    )
