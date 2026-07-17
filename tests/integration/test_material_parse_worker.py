from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfWriter
from sqlalchemy import func, select

from apps.api.assets.material_parser import FakeMaterialParser, ParseLimits
from apps.api.assets.models import MaterialParseVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.jobs.models import GenerationJob
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry, OutboxEvent
from apps.api.settings import Settings
from apps.api.uploads.confirmation_service import UploadConfirmationService
from apps.api.uploads.schemas import ConfirmUploadRequest, CreateUploadSessionRequest
from apps.api.uploads.session_service import UploadSessionService
from tests.fakes.identity import seed_test_actor
from tests.fakes.object_storage import FakeObjectStorage
from workers.material_parse import MaterialParseJobRunner


def generated_pdf() -> bytes:
    import io

    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


def test_worker_persists_one_parse_version_and_cleans_temp_files(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    payload = generated_pdf()
    checksum = hashlib.sha256(payload).hexdigest()
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
        upload = UploadSessionService(
            session=session,
            storage=storage,
            actor=actor,
            bucket="shanhaiedu",
            ttl_seconds=900,
            max_size_bytes=10_000,
        ).create_session(
            project.id,
            CreateUploadSessionRequest(
                filename="generated.pdf",
                media_type="application/pdf",
                size_bytes=len(payload),
                sha256=checksum,
            ),
            idempotency_key="parse-worker-upload",
            request_id="req-parse-worker-upload",
        )
        assert storage.last_presigned is not None
        storage.put_bytes(
            bucket=storage.last_presigned.bucket,
            key=storage.last_presigned.key,
            payload=payload,
            media_type="application/pdf",
        )
        job = UploadConfirmationService(
            session=session,
            storage=storage,
            actor=actor,
        ).confirm(
            project_id=project.id,
            material_id=upload.material_id,
            idempotency_key="parse-worker-confirm",
            payload=ConfirmUploadRequest(
                upload_session_id=upload.upload_session_id,
                etag=storage.stat(
                    bucket=storage.last_presigned.bucket,
                    key=storage.last_presigned.key,
                ).etag,
                size_bytes=len(payload),
                sha256=checksum,
            ),
            request_id="req-parse-worker-confirm",
            idempotency_ttl_seconds=900,
        )

    runner = MaterialParseJobRunner(
        factory,
        storage=storage,
        parser=FakeMaterialParser(page_texts=("First", "Second")),
        limits=ParseLimits(),
        temp_root=tmp_path,
        settings=Settings(_env_file=None, environment="test"),
    )
    assert runner.run(job.job_id, worker_id="parse-worker-1") == "succeeded"
    assert runner.run(job.job_id, worker_id="parse-worker-2") == "ignored"
    assert list(tmp_path.iterdir()) == []

    with factory() as session:
        parse = session.scalar(select(MaterialParseVersion))
        persisted_job = session.get(GenerationJob, job.job_id)
        assert parse is not None and parse.status == "succeeded"
        assert parse.generation_job_id == job.job_id
        assert parse.page_count == 2
        assert persisted_job is not None and persisted_job.status == "succeeded"
        assert session.scalar(select(func.count()).select_from(MaterialParseVersion)) == 1
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) >= 4
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) >= 4
