from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.context import ActorContext, system_actor
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobService
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.models import EventStreamEntry
from apps.api.uploads.models import SourceMaterial
from tests.fakes.identity import seed_test_actor


def seed_queued_job(session) -> tuple[GenerationJob, ActorContext]:
    actor = seed_test_actor(session)
    project = ProjectRepository(session, actor).create(
        CreateProjectRequest(title="Fractions", knowledge_point="One half")
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
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    job = GenerationJob(
        id=new_uuid7(),
        organization_id=SYSTEM_ORGANIZATION_ID,
        project_id=project.id,
        source_material_id=material.id,
        job_type="material.parse",
        status="queued",
        progress_percent=0,
        priority=100,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(material)
    session.flush()
    session.add(job)
    session.flush()
    EventWriter(session, SYSTEM_ORGANIZATION_ID).append(
        project_id=project.id,
        event_type="generation.job.queued",
        resource=EventResource(type="generation_job", id=job.id),
        payload={"status": "queued"},
        request_id="req-seed-job",
    )
    return job, actor


def test_expired_worker_lease_is_recovered_and_duplicate_delivery_is_absorbed(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        job, _ = seed_queued_job(session)
        job_id = job.id
    worker_actor = system_actor(SYSTEM_ORGANIZATION_ID)

    with factory() as session, session.begin():
        first = GenerationJobService(
            session, actor=worker_actor, idempotency_ttl_seconds=900
        ).claim(job_id, worker_id="worker-1", lease_seconds=5)
        assert first is not None and first.status == "running"

    with factory() as session, session.begin():
        duplicate_active = GenerationJobService(
            session, actor=worker_actor, idempotency_ttl_seconds=900
        ).claim(job_id, worker_id="worker-2", lease_seconds=5)
        assert duplicate_active is None

    with factory() as session, session.begin():
        persisted = session.get(GenerationJob, job_id, with_for_update=True)
        assert persisted is not None
        persisted.lease_expires_at = utc_now() - timedelta(seconds=1)

    with factory() as session, session.begin():
        recovered = GenerationJobService(
            session, actor=worker_actor, idempotency_ttl_seconds=900
        ).claim(job_id, worker_id="worker-2", lease_seconds=5)
        assert recovered is not None
        assert recovered.attempt_count == 2
        assert recovered.lease_owner == "worker-2"

    with factory() as session, session.begin():
        completed = GenerationJobService(
            session, actor=worker_actor, idempotency_ttl_seconds=900
        ).complete(job_id, worker_id="worker-2")
        assert completed is not None and completed.status == "succeeded"

    with factory() as session, session.begin():
        duplicate = GenerationJobService(
            session, actor=worker_actor, idempotency_ttl_seconds=900
        ).complete(job_id, worker_id="worker-2")
        assert duplicate is not None and duplicate.status == "succeeded"

    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(EventStreamEntry)
                .where(EventStreamEntry.resource_id == job_id)
            )
            == 4
        )


def test_cancel_requested_before_claim_finishes_as_cancelled(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        job, actor = seed_queued_job(session)
        job_id = job.id

    with factory() as session, session.begin():
        cancelled = GenerationJobService(
            session,
            actor=actor,
            idempotency_ttl_seconds=900,
        ).request_cancel(
            job_id,
            idempotency_key="cancel-before-claim",
            request_id="req-cancel-before-claim",
        )
        assert cancelled.status == "cancel_requested"

    with factory() as session, session.begin():
        claimed = GenerationJobService(
            session,
            actor=system_actor(SYSTEM_ORGANIZATION_ID),
            idempotency_ttl_seconds=900,
        ).claim(job_id, worker_id="worker-after-cancel", lease_seconds=5)
        assert claimed is None

    with factory() as session:
        persisted = session.get(GenerationJob, job_id)
        assert persisted is not None
        assert persisted.status == "cancelled"
        assert persisted.attempt_count == 0
