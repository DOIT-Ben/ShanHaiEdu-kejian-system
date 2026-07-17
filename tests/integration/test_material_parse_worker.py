from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from uuid import UUID

from pypdf import PdfWriter
from sqlalchemy import func, select

from apps.api.assets.material_parser import (
    FakeMaterialParser,
    MaterialParseResult,
    MaterialParseSource,
    ParseLimits,
)
from apps.api.assets.models import MaterialParseVersion
from apps.api.assets.pypdf_parser import PypdfMaterialParser
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.context import ActorContext, system_actor
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobService
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


class CallbackParser:
    name = "fake-material-parser"
    version = "1.0"

    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback

    def parse(
        self,
        path: Path,
        source: MaterialParseSource,
        limits: ParseLimits,
    ) -> MaterialParseResult:
        self._callback()
        return FakeMaterialParser(page_texts=("First", "Second")).parse(path, source, limits)


def seed_material_job(
    factory,
    storage: FakeObjectStorage,
    payload: bytes,
    *,
    key_suffix: str,
) -> tuple[ActorContext, UUID]:
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
            idempotency_key=f"parse-worker-upload-{key_suffix}",
            request_id=f"req-parse-worker-upload-{key_suffix}",
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
            idempotency_key=f"parse-worker-confirm-{key_suffix}",
            payload=ConfirmUploadRequest(
                upload_session_id=upload.upload_session_id,
                etag=storage.stat(
                    bucket=storage.last_presigned.bucket,
                    key=storage.last_presigned.key,
                ).etag,
                size_bytes=len(payload),
                sha256=checksum,
            ),
            request_id=f"req-parse-worker-confirm-{key_suffix}",
            idempotency_ttl_seconds=900,
        )
    return actor, job.job_id


def runner(
    factory,
    storage: FakeObjectStorage,
    parser,
    temp_root: Path,
) -> MaterialParseJobRunner:
    return MaterialParseJobRunner(
        factory,
        storage=storage,
        parser=parser,
        limits=ParseLimits(),
        temp_root=temp_root,
        settings=Settings(_env_file=None, environment="test"),
    )


def test_worker_persists_one_parse_version_and_cleans_temp_files(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    payload = generated_pdf()
    _, job_id = seed_material_job(factory, storage, payload, key_suffix="success")
    worker = runner(
        factory,
        storage,
        FakeMaterialParser(page_texts=("First", "Second")),
        tmp_path,
    )
    assert worker.run(job_id, worker_id="parse-worker-1") == "succeeded"
    assert worker.run(job_id, worker_id="parse-worker-2") == "ignored"
    assert list(tmp_path.iterdir()) == []

    with factory() as session:
        parse = session.scalar(select(MaterialParseVersion))
        persisted_job = session.get(GenerationJob, job_id)
        assert parse is not None and parse.status == "succeeded"
        assert parse.generation_job_id == job_id
        assert parse.page_count == 2
        assert persisted_job is not None and persisted_job.status == "succeeded"
        assert session.scalar(select(func.count()).select_from(MaterialParseVersion)) == 1
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) >= 4
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) >= 4


def test_worker_parses_generated_pdf_with_real_local_adapter(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    _, job_id = seed_material_job(
        factory,
        storage,
        generated_pdf(),
        key_suffix="real-local",
    )

    result = runner(factory, storage, PypdfMaterialParser(), tmp_path).run(
        job_id,
        worker_id="parse-worker-real-local",
    )

    assert result == "succeeded"
    assert list(tmp_path.iterdir()) == []
    with factory() as session:
        parse = session.scalar(select(MaterialParseVersion))
        assert parse is not None and parse.status == "succeeded"
        assert parse.parser_name == "pypdf"
        assert parse.page_count == 2
        assert parse.content_json is not None
        assert [page["page_number"] for page in parse.content_json["pages"]] == [1, 2]


def test_worker_failure_is_classified_and_temp_files_are_removed(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    _, job_id = seed_material_job(factory, storage, generated_pdf(), key_suffix="failure")

    result = runner(
        factory,
        storage,
        FakeMaterialParser(error_code="PDF_DAMAGED"),
        tmp_path,
    ).run(job_id, worker_id="parse-worker-failure")

    assert result == "failed"
    assert list(tmp_path.iterdir()) == []
    with factory() as session:
        parse = session.scalar(select(MaterialParseVersion))
        job = session.get(GenerationJob, job_id)
        assert parse is not None and parse.status == "failed"
        assert parse.error_code == "PDF_DAMAGED"
        assert parse.validation_report_json["valid"] is False
        assert job is not None and job.status == "failed"
        assert job.error_code == "PDF_DAMAGED"


def test_cancel_during_parse_finishes_job_and_parse_without_success_evidence(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    actor, job_id = seed_material_job(factory, storage, generated_pdf(), key_suffix="cancel")

    def cancel() -> None:
        with factory() as session, session.begin():
            GenerationJobService(session, actor=actor, idempotency_ttl_seconds=900).request_cancel(
                job_id,
                idempotency_key="cancel-material-parse",
                request_id="req-cancel-material-parse",
            )

    result = runner(factory, storage, CallbackParser(cancel), tmp_path).run(
        job_id,
        worker_id="parse-worker-cancel",
    )

    assert result == "cancelled"
    assert list(tmp_path.iterdir()) == []
    with factory() as session:
        parse = session.scalar(select(MaterialParseVersion))
        job = session.get(GenerationJob, job_id)
        assert parse is not None and parse.status == "failed"
        assert parse.error_code == "PDF_PARSE_CANCELLED"
        assert parse.content_json is None
        assert job is not None and job.status == "cancelled"


def test_stale_worker_cannot_commit_after_lease_takeover_and_recovery_is_idempotent(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    actor, job_id = seed_material_job(factory, storage, generated_pdf(), key_suffix="takeover")

    def take_over_lease() -> None:
        with factory() as session, session.begin():
            job = session.get(GenerationJob, job_id, with_for_update=True)
            assert job is not None
            job.lease_expires_at = utc_now() - timedelta(seconds=1)
        with factory() as session, session.begin():
            claimed = GenerationJobService(
                session,
                actor=system_actor(actor.organization_id),
                idempotency_ttl_seconds=900,
            ).claim(job_id, worker_id="parse-worker-winner", lease_seconds=60)
            assert claimed is not None

    stale_result = runner(factory, storage, CallbackParser(take_over_lease), tmp_path).run(
        job_id,
        worker_id="parse-worker-stale",
    )
    assert stale_result == "ignored"

    recovered_result = runner(
        factory,
        storage,
        FakeMaterialParser(page_texts=("Recovered",)),
        tmp_path,
    ).run(job_id, worker_id="parse-worker-winner")
    assert recovered_result == "succeeded"
    assert list(tmp_path.iterdir()) == []

    with factory() as session:
        parse = session.scalar(select(MaterialParseVersion))
        job = session.get(GenerationJob, job_id)
        assert parse is not None and parse.status == "succeeded"
        assert parse.generation_job_id == job_id
        assert parse.page_count == 1
        assert job is not None and job.status == "succeeded"
        assert session.scalar(select(func.count()).select_from(MaterialParseVersion)) == 1
