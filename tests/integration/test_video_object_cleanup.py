from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.creation.models import GenerationResult
from apps.api.database import build_engine, build_session_factory
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.model_gateway.audit_models import GenerationAttempt
from apps.api.model_gateway.contracts import VideoResultScope
from apps.api.model_gateway.object_storage_video_store import (
    build_video_final_key,
    build_video_staging_key,
)
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.video_golden_slice_support import (
    seed_completed_candidate,
    seed_video_project,
)
from workers.video_object_cleanup import VideoObjectCleanupCoordinator


async def test_video_gc_uses_postgresql_truth_for_failed_job_objects(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    now = datetime(2026, 7, 31, 3, 0, tzinfo=UTC)
    with factory() as session, session.begin():
        completed = seed_completed_candidate(session, seeded, lesson_index=0)
        result = session.get(GenerationResult, completed.result_id)
        assert result is not None
        job = session.get(GenerationJob, result.generation_job_id)
        assert job is not None and job.lesson_unit_id is not None
        job.status = "failed"
        job.progress_message = "Video generation failed"
        job.error_code = "MODEL_REJECTED"
        job.finished_at = now - timedelta(days=8)
        scope = VideoResultScope(
            organization_id=job.organization_id,
            project_id=seeded.project_id,
            lesson_unit_id=job.lesson_unit_id,
            generation_job_id=job.id,
        )
        conflicting_final_key = build_video_final_key(scope, sha256="d" * 64)
        conflicting_asset = FileAsset(
            id=new_uuid7(),
            organization_id=job.organization_id,
            asset_key=f"video-gc-conflict:{job.id}",
            asset_kind="video",
            status="active",
            retention_class="project_asset",
            created_by=seeded.actor.principal_id,
            updated_by=seeded.actor.principal_id,
        )
        session.add(conflicting_asset)
        session.flush()
        conflicting_version = FileAssetVersion(
            id=new_uuid7(),
            organization_id=job.organization_id,
            file_asset_id=conflicting_asset.id,
            version_no=1,
            storage_bucket="shanhaiedu",
            storage_key=conflicting_final_key,
            mime_type="video/mp4",
            byte_size=5,
            sha256="e" * 64,
            etag="video-gc-conflict",
            width=1280,
            height=720,
            duration_ms=6000,
            scan_status="clean",
            metadata_json={"runtime": "video.golden_slice", "generation_job_id": str(job.id)},
            derived_from_version_id=completed.file_asset_version_id,
            created_at=now,
            created_by=seeded.actor.principal_id,
        )
        session.add(conflicting_version)
        session.flush()
        conflicting_asset.current_version_id = conflicting_version.id

    storage = FakeObjectStorage()
    staging_key = build_video_staging_key(
        scope,
        provider_name="deterministic-fake",
        provider_task_id="failed-private-task",
    )
    final_key = build_video_final_key(scope, sha256="a" * 64)
    _put_old(storage, staging_key, now=now, age=timedelta(days=2))
    _put_old(storage, final_key, now=now, age=timedelta(days=8), payload=b"unbound-final")
    _put_old(
        storage,
        conflicting_final_key,
        now=now,
        age=timedelta(days=8),
        payload=b"conflict-final",
    )

    outcome = VideoObjectCleanupCoordinator(
        factory,
        storage,
        bucket="shanhaiedu",
    ).cleanup(now=now, dry_run=False)

    assert outcome.candidate_count == 2
    assert outcome.deleted_count == 2
    assert storage.object_count == 1
    assert storage.stat(bucket="shanhaiedu", key=conflicting_final_key).key == conflicting_final_key
    engine.dispose()


async def test_video_gc_preserves_exact_bound_final_but_cleans_success_staging(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    now = datetime(2026, 7, 31, 4, 0, tzinfo=UTC)
    with factory() as session, session.begin():
        completed = seed_completed_candidate(session, seeded, lesson_index=0)
        result = session.get(GenerationResult, completed.result_id)
        source_version = session.get(FileAssetVersion, completed.file_asset_version_id)
        assert result is not None and source_version is not None
        job = session.get(GenerationJob, result.generation_job_id)
        assert job is not None and job.lesson_unit_id is not None
        scope = VideoResultScope(
            organization_id=job.organization_id,
            project_id=seeded.project_id,
            lesson_unit_id=job.lesson_unit_id,
            generation_job_id=job.id,
        )
        final_key = build_video_final_key(scope, sha256=source_version.sha256)
        asset = FileAsset(
            id=new_uuid7(),
            organization_id=job.organization_id,
            asset_key=f"video-gc-bound:{job.id}",
            asset_kind="video",
            status="active",
            retention_class="project_asset",
            created_by=seeded.actor.principal_id,
            updated_by=seeded.actor.principal_id,
        )
        session.add(asset)
        session.flush()
        bound_version = FileAssetVersion(
            id=new_uuid7(),
            organization_id=job.organization_id,
            file_asset_id=asset.id,
            version_no=1,
            storage_bucket="shanhaiedu",
            storage_key=final_key,
            mime_type="video/mp4",
            byte_size=source_version.byte_size,
            sha256=source_version.sha256,
            etag="video-gc-bound",
            width=source_version.width,
            height=source_version.height,
            duration_ms=source_version.duration_ms,
            scan_status="clean",
            metadata_json={"runtime": "video.golden_slice", "generation_job_id": str(job.id)},
            derived_from_version_id=source_version.derived_from_version_id,
            created_at=now,
            created_by=seeded.actor.principal_id,
        )
        session.add(bound_version)
        session.flush()
        asset.current_version_id = bound_version.id

    storage = FakeObjectStorage()
    staging_key = build_video_staging_key(
        scope,
        provider_name="deterministic-fake",
        provider_task_id="succeeded-private-task",
    )
    unbound_success_final_key = build_video_final_key(scope, sha256="c" * 64)
    _put_old(storage, staging_key, now=now, age=timedelta(days=2))
    _put_old(storage, final_key, now=now, age=timedelta(days=8), payload=b"bound-final")
    _put_old(
        storage,
        unbound_success_final_key,
        now=now,
        age=timedelta(days=8),
        payload=b"unbound-success-final",
    )

    outcome = VideoObjectCleanupCoordinator(
        factory,
        storage,
        bucket="shanhaiedu",
    ).cleanup(now=now, dry_run=False)

    assert outcome.deleted_count == 1
    assert storage.stat(bucket="shanhaiedu", key=final_key).key == final_key
    assert (
        storage.stat(bucket="shanhaiedu", key=unbound_success_final_key).key
        == unbound_success_final_key
    )
    engine.dispose()


async def test_video_gc_waits_for_active_attempt_after_job_lease_expiry(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    now = datetime(2026, 7, 31, 5, 0, tzinfo=UTC)
    with factory() as session, session.begin():
        completed = seed_completed_candidate(session, seeded, lesson_index=0)
        result = session.get(GenerationResult, completed.result_id)
        assert result is not None
        job = session.get(GenerationJob, result.generation_job_id)
        assert job is not None and job.node_run_id is not None and job.lesson_unit_id is not None
        job.status = "running"
        job.finished_at = None
        job.lease_owner = "expired-worker"
        job.lease_expires_at = now - timedelta(hours=1)
        scope = VideoResultScope(
            organization_id=job.organization_id,
            project_id=seeded.project_id,
            lesson_unit_id=job.lesson_unit_id,
            generation_job_id=job.id,
        )
        attempt = GenerationAttempt(
            id=new_uuid7(),
            organization_id=job.organization_id,
            project_id=seeded.project_id,
            node_run_id=job.node_run_id,
            generation_job_id=job.id,
            attempt_no=1,
            request_id=f"video-gc-active:{job.id}",
            capability="video.image_to_video.6s_30s",
            operation_kind="video_poll",
            provider_name="deterministic-fake",
            provider_model="fake-video",
            route_reason="primary",
            status="running",
            request_hash="b" * 64,
            provider_request_id=f"video-gc-provider:{job.id}",
            provider_task_id="active-private-task",
            lease_owner="active-worker",
            lease_expires_at=now + timedelta(hours=1),
            heartbeat_at=now,
            submitted_at=now - timedelta(hours=2),
            error_details_json={},
        )
        session.add(attempt)

    storage = FakeObjectStorage()
    staging_key = build_video_staging_key(
        scope,
        provider_name="deterministic-fake",
        provider_task_id="active-private-task",
    )
    _put_old(storage, staging_key, now=now, age=timedelta(days=2))
    coordinator = VideoObjectCleanupCoordinator(factory, storage, bucket="shanhaiedu")

    retained = coordinator.cleanup(now=now, dry_run=False)

    assert retained.deleted_count == 0
    assert storage.object_count == 1

    with factory() as session, session.begin():
        current = session.get(GenerationAttempt, attempt.id)
        assert current is not None
        current.status = "failed"
        current.finished_at = now
        current.error_code = "LEASE_EXPIRED"
        current.latency_ms = 1
        current.lease_owner = None
        current.lease_expires_at = None

    deleted = coordinator.cleanup(now=now, dry_run=False)

    assert deleted.deleted_count == 1
    assert storage.object_count == 0
    engine.dispose()


def _put_old(
    storage: FakeObjectStorage,
    key: str,
    *,
    now: datetime,
    age: timedelta,
    payload: bytes = b"video",
) -> None:
    metadata = storage.put_bytes(
        bucket="shanhaiedu",
        key=key,
        payload=payload,
        media_type="video/mp4",
    )
    storage.put_at(
        bucket="shanhaiedu",
        key=key,
        metadata=replace(metadata, last_modified=now - age),
    )
