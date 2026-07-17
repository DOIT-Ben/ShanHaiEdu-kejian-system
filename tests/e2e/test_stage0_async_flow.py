from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
from sqlalchemy import select

from apps.api.assets.material_parser import FakeMaterialParser, ParseLimits
from apps.api.assets.models import MaterialParseVersion
from apps.api.database import build_session_factory
from apps.api.jobs.models import GenerationJob
from apps.api.main import create_app
from apps.api.reliability.models import OutboxEvent
from apps.api.reliability.outbox import OutboxDispatcher
from apps.api.reliability.sse import EventReplayRepository
from apps.api.settings import Settings
from tests.conftest import run_migration
from tests.fakes.identity import configure_test_identity
from tests.fakes.object_storage import FakeObjectStorage
from workers.material_parse import MaterialParseJobRunner

PDF_PAYLOAD = b"%PDF-fake"
SHA256 = hashlib.sha256(PDF_PAYLOAD).hexdigest()


async def test_project_upload_worker_sse_and_rest_reconciliation(
    postgres_database_url: str,
    tmp_path: Path,
) -> None:
    run_migration(postgres_database_url, "head")
    storage = FakeObjectStorage()
    settings = Settings(_env_file=None, environment="test", database_url=postgres_database_url)
    app = create_app(settings=settings, object_storage=storage)
    configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_response = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "e2e-project-001"},
                json={"title": "Fractions", "knowledge_point": "One half"},
            )
            project_id = project_response.json()["data"]["id"]
            upload_response = await client.post(
                f"/api/v2/projects/{project_id}/materials/uploads",
                headers={"Idempotency-Key": "e2e-upload-001"},
                json={
                    "filename": "lesson.pdf",
                    "media_type": "application/pdf",
                    "size_bytes": len(PDF_PAYLOAD),
                    "sha256": SHA256,
                },
            )
            upload = upload_response.json()["data"]
            upload_replay = await client.post(
                f"/api/v2/projects/{project_id}/materials/uploads",
                headers={"Idempotency-Key": "e2e-upload-001"},
                json={
                    "filename": "lesson.pdf",
                    "media_type": "application/pdf",
                    "size_bytes": len(PDF_PAYLOAD),
                    "sha256": SHA256,
                },
            )
            assert upload_replay.json()["data"] == upload
            assert storage.last_presigned is not None
            uploaded = storage.put_bytes(
                bucket=storage.last_presigned.bucket,
                key=storage.last_presigned.key,
                payload=PDF_PAYLOAD,
                media_type="application/pdf",
            )
            confirm_response = await client.post(
                f"/api/v2/projects/{project_id}/materials/{upload['material_id']}/confirm",
                headers={"Idempotency-Key": "e2e-confirm-001"},
                json={
                    "upload_session_id": upload["upload_session_id"],
                    "etag": uploaded.etag,
                    "size_bytes": len(PDF_PAYLOAD),
                    "sha256": SHA256,
                },
            )
            assert confirm_response.status_code == 202
            job_id = confirm_response.json()["data"]["job_id"]

        factory = build_session_factory(app.state.database_engine)

        def publish(event: OutboxEvent) -> None:
            if event.topic != "generation.job.queued":
                return
            result = MaterialParseJobRunner(
                factory,
                storage=storage,
                parser=FakeMaterialParser(page_texts=("One half",)),
                limits=ParseLimits(),
                settings=settings,
                temp_root=tmp_path,
            ).run(event.aggregate_id, worker_id="e2e-worker")
            assert result == "succeeded"

        dispatcher = OutboxDispatcher(
            factory,
            worker_id="e2e-dispatcher",
            lease_seconds=30,
            retry_seconds=1,
        )
        assert dispatcher.dispatch_batch(publish) == 4

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            job_response = await client.get(f"/api/v2/generation-jobs/{job_id}")
        assert job_response.json()["data"]["status"] == "succeeded"

        with factory() as session:
            job = session.get(GenerationJob, job_id)
            assert job is not None and job.project_id is not None
            parse = session.scalar(select(MaterialParseVersion))
            assert parse is not None
            assert parse.generation_job_id == job.id
            assert parse.status == "succeeded"
            events = EventReplayRepository(session, job.organization_id).replay(
                project_id=job.project_id,
                after_sequence=0,
                resource=("generation_job", job.id),
            )
            assert [event.summary_json["payload"]["status"] for event in events] == [
                "queued",
                "running",
                "running",
                "running",
                "succeeded",
            ]
    finally:
        app.state.database_engine.dispose()
