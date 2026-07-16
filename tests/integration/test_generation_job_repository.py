from __future__ import annotations

from apps.api.database import build_engine, build_session_factory
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.repository import GenerationJobRepository
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.uploads.models import SourceMaterial


def test_job_facts_do_not_require_redis(migrated_database_url: str) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            project = ProjectRepository(
                session, SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID
            ).create(
                CreateProjectRequest(
                    title="Fractions",
                    knowledge_point="Understanding one half",
                )
            )
            material = SourceMaterial(
                id=new_uuid7(),
                organization_id=SYSTEM_ORGANIZATION_ID,
                project_id=project.id,
                material_kind="textbook",
                file_asset_id=None,
                original_filename="lesson.pdf",
                mime_type="application/pdf",
                upload_status="pending_upload",
                created_by=SYSTEM_PRINCIPAL_ID,
                updated_by=SYSTEM_PRINCIPAL_ID,
            )
            session.add(material)
            session.flush()
            job = GenerationJob(
                id=new_uuid7(),
                organization_id=SYSTEM_ORGANIZATION_ID,
                project_id=project.id,
                source_material_id=material.id,
                job_type="material.inspect",
                status="queued",
                progress_percent=0,
                priority=100,
                created_by=SYSTEM_PRINCIPAL_ID,
                updated_by=SYSTEM_PRINCIPAL_ID,
            )
            session.add(job)
        job_id = job.id

    with factory() as session:
        persisted = GenerationJobRepository(session, SYSTEM_ORGANIZATION_ID).get(job_id)
        assert persisted is not None
        assert persisted.status == "queued"
