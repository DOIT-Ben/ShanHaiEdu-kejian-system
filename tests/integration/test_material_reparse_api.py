from __future__ import annotations

import asyncio
from secrets import token_urlsafe

import httpx
from sqlalchemy import func, select

from apps.api.assets.models import MaterialParseVersion
from apps.api.database import build_engine, build_session_factory
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.main import create_app
from apps.api.reliability.models import OutboxEvent
from apps.api.settings import Settings
from tests.fakes.identity import override_test_identity
from tests.integration.identity_session_support import APP_ORIGIN, login, runtime_settings
from tests.integration.material_reparse_support import (
    SeededMaterialParse,
    seed_foreign_material_parse,
    seed_material_parse,
)


def retry_path(seeded: SeededMaterialParse, *, project_id: object | None = None) -> str:
    resolved_project_id = project_id or seeded.project_id
    return f"/api/v2/projects/{resolved_project_id}/materials/{seeded.material_id}/parse-versions"


def retry_payload(
    seeded: SeededMaterialParse, *, version_id: object | None = None
) -> dict[str, str]:
    return {"file_asset_version_id": str(version_id or seeded.file_asset_version_id)}


def build_test_app(database_url: str, factory, seeded: SeededMaterialParse):
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=database_url,
            session_access_code=None,
            session_allowed_origins=[],
            session_csrf_secret=None,
            session_teacher_principal_id=None,
        ),
        session_factory=factory,
    )
    override_test_identity(app, seeded.actor)
    return app


async def test_retry_failed_parse_creates_one_exact_job_and_preserves_history(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = seed_material_parse(factory)
    app = build_test_app(migrated_database_url, factory, seeded)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.post(
                retry_path(seeded),
                headers={"Idempotency-Key": "retry-failed-material"},
                json=retry_payload(seeded),
            )
            replay = await client.post(
                retry_path(seeded),
                headers={"Idempotency-Key": "retry-failed-material"},
                json=retry_payload(seeded),
            )

        assert first.status_code == 202, first.text
        assert replay.status_code == 202, replay.text
        assert replay.json()["data"] == first.json()["data"]
        new_job_id = first.json()["data"]["job_id"]
        with factory() as session:
            old_job = session.get(GenerationJob, seeded.generation_job_id)
            old_parse = session.get(MaterialParseVersion, seeded.parse_version_id)
            jobs = list(
                session.scalars(
                    select(GenerationJob)
                    .where(GenerationJob.source_material_id == seeded.material_id)
                    .order_by(GenerationJob.created_at)
                )
            )
            queued_event = session.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.topic == "generation.job.queued",
                    OutboxEvent.aggregate_id == new_job_id,
                )
            )
        assert old_job is not None and old_job.status == "failed"
        assert old_job.error_code == "PDF_DAMAGED"
        assert old_parse is not None and old_parse.status == "failed"
        assert old_parse.error_code == "PDF_DAMAGED"
        assert len(jobs) == 2
        assert jobs[-1].status == "queued"
        assert jobs[-1].creation_request_json == {
            "file_asset_version_id": str(seeded.file_asset_version_id)
        }
        assert queued_event is not None
    finally:
        engine.dispose()


async def test_retry_hides_cross_project_and_cross_tenant_and_rejects_wrong_version(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = seed_material_parse(factory)
    other_project = seed_material_parse(factory, actor=seeded.actor, title="Other project")
    foreign = seed_foreign_material_parse(factory)
    app = build_test_app(migrated_database_url, factory, seeded)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            cross_project = await client.post(
                retry_path(seeded, project_id=other_project.project_id),
                headers={"Idempotency-Key": "retry-cross-project"},
                json=retry_payload(seeded),
            )
            cross_tenant = await client.post(
                retry_path(foreign),
                headers={"Idempotency-Key": "retry-cross-tenant"},
                json=retry_payload(foreign),
            )
            wrong_version = await client.post(
                retry_path(seeded),
                headers={"Idempotency-Key": "retry-wrong-version"},
                json=retry_payload(seeded, version_id=other_project.file_asset_version_id),
            )

        assert cross_project.status_code == 404
        assert cross_tenant.status_code == 404
        assert wrong_version.status_code == 409
    finally:
        engine.dispose()


async def test_retry_rejects_successful_parse_and_an_existing_active_job(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    failed = seed_material_parse(factory)
    succeeded = seed_material_parse(
        factory,
        actor=failed.actor,
        parse_status="succeeded",
        title="Successful material",
    )
    with factory() as session, session.begin():
        session.add(
            GenerationJob(
                id=new_uuid7(),
                organization_id=failed.actor.organization_id,
                project_id=failed.project_id,
                source_material_id=failed.material_id,
                creation_request_json={"file_asset_version_id": str(failed.file_asset_version_id)},
                job_type="material.parse",
                status="running",
                progress_percent=20,
                progress_message="Parsing material",
                idempotency_key="already-active-parse",
                request_hash="d" * 64,
                priority=100,
                created_by=failed.actor.principal_id,
                updated_by=failed.actor.principal_id,
            )
        )
    app = build_test_app(migrated_database_url, factory, failed)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            successful = await client.post(
                retry_path(succeeded),
                headers={"Idempotency-Key": "retry-successful-parse"},
                json=retry_payload(succeeded),
            )
            active = await client.post(
                retry_path(failed),
                headers={"Idempotency-Key": "retry-active-parse"},
                json=retry_payload(failed),
            )

        assert successful.status_code == 409
        assert active.status_code == 409
    finally:
        engine.dispose()


async def test_concurrent_retry_requests_create_only_one_new_job(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = seed_material_parse(factory)
    app = build_test_app(migrated_database_url, factory, seeded)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                client.post(
                    retry_path(seeded),
                    headers={"Idempotency-Key": "retry-concurrent-first"},
                    json=retry_payload(seeded),
                ),
                client.post(
                    retry_path(seeded),
                    headers={"Idempotency-Key": "retry-concurrent-second"},
                    json=retry_payload(seeded),
                ),
            )

        assert sorted(response.status_code for response in responses) == [202, 409]
        with factory() as session:
            job_count = session.scalar(
                select(func.count())
                .select_from(GenerationJob)
                .where(GenerationJob.source_material_id == seeded.material_id)
            )
        assert job_count == 2
    finally:
        engine.dispose()


async def test_retry_requires_session_csrf_and_logout_invalidates_write(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    seeded = seed_material_parse(factory)
    access_code = token_urlsafe(32)
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=access_code,
            csrf_secret=token_urlsafe(48),
        ),
        session_factory=factory,
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50421)),
            base_url=APP_ORIGIN,
        ) as client:
            anonymous = await client.post(
                retry_path(seeded),
                headers={"Idempotency-Key": "retry-auth-anonymous"},
                json=retry_payload(seeded),
            )
            created = await login(client, access_code)
            assert created.status_code == 201, created.text
            csrf_token = created.json()["data"]["csrf_token"]
            missing_csrf = await client.post(
                retry_path(seeded),
                headers={"Idempotency-Key": "retry-auth-no-csrf", "Origin": APP_ORIGIN},
                json=retry_payload(seeded),
            )
            logout = await client.delete(
                "/api/v2/auth/session",
                headers={"Origin": APP_ORIGIN, "X-CSRF-Token": csrf_token},
            )
            after_logout = await client.post(
                retry_path(seeded),
                headers={
                    "Idempotency-Key": "retry-auth-after-logout",
                    "Origin": APP_ORIGIN,
                    "X-CSRF-Token": csrf_token,
                },
                json=retry_payload(seeded),
            )

        assert anonymous.status_code == 401
        assert anonymous.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
        assert logout.status_code == 204
        assert after_logout.status_code == 401
        assert after_logout.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    finally:
        engine.dispose()
