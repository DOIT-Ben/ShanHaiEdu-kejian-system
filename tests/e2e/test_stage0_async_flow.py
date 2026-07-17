from __future__ import annotations

import httpx

from apps.api.database import build_session_factory
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobService
from apps.api.main import create_app
from apps.api.reliability.models import OutboxEvent
from apps.api.reliability.outbox import OutboxDispatcher
from apps.api.reliability.sse import EventReplayRepository
from apps.api.settings import Settings
from apps.api.uploads.storage import ObjectMetadata
from tests.conftest import run_migration
from tests.fakes.object_storage import FakeObjectStorage

SHA256 = "a" * 64


async def test_project_upload_worker_sse_and_rest_reconciliation(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    storage = FakeObjectStorage()
    settings = Settings(_env_file=None, environment="test", database_url=postgres_database_url)
    app = create_app(settings=settings, object_storage=storage)
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
                    "size_bytes": 4,
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
                    "size_bytes": 4,
                    "sha256": SHA256,
                },
            )
            assert upload_replay.json()["data"] == upload
            assert storage.last_presigned is not None
            storage.put(
                ObjectMetadata(
                    bucket=storage.last_presigned.bucket,
                    key=storage.last_presigned.key,
                    etag="etag-e2e",
                    size_bytes=4,
                    media_type="application/pdf",
                    sha256=SHA256,
                )
            )
            confirm_response = await client.post(
                f"/api/v2/projects/{project_id}/materials/{upload['material_id']}/confirm",
                headers={"Idempotency-Key": "e2e-confirm-001"},
                json={
                    "upload_session_id": upload["upload_session_id"],
                    "etag": "etag-e2e",
                    "size_bytes": 4,
                    "sha256": SHA256,
                },
            )
            assert confirm_response.status_code == 202
            job_id = confirm_response.json()["data"]["job_id"]

        factory = build_session_factory(app.state.database_engine)

        def publish(event: OutboxEvent) -> None:
            if event.topic != "generation.job.queued":
                return
            with factory() as session, session.begin():
                service = GenerationJobService(session, idempotency_ttl_seconds=900)
                claimed = service.claim(
                    event.aggregate_id, worker_id="e2e-worker", lease_seconds=30
                )
                assert claimed is not None
            with factory() as session, session.begin():
                service = GenerationJobService(session, idempotency_ttl_seconds=900)
                service.update_progress(
                    event.aggregate_id,
                    worker_id="e2e-worker",
                    progress_percent=50,
                    message="Deterministic progress",
                )
            with factory() as session, session.begin():
                GenerationJobService(session, idempotency_ttl_seconds=900).complete(
                    event.aggregate_id, worker_id="e2e-worker"
                )

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
            events = EventReplayRepository(session).replay(
                project_id=job.project_id,
                after_sequence=0,
                resource=("generation_job", job.id),
            )
            assert [event.summary_json["payload"]["status"] for event in events] == [
                "queued",
                "running",
                "running",
                "succeeded",
            ]
    finally:
        app.state.database_engine.dispose()
