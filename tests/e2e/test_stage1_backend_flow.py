from __future__ import annotations

import hashlib
import io
import os
import subprocess
import time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from pypdf import PdfWriter
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select

from apps.api.artifacts.models import Artifact, ArtifactRelation
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.service import ArtifactService
from apps.api.assets.models import FileAssetVersion, MaterialParseVersion
from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
    ReplaceMode,
)
from apps.api.assets.project_models import AssetBinding
from apps.api.assets.project_service import ProjectAssetService
from apps.api.assets.pypdf_parser import PypdfMaterialParser
from apps.api.content_runtime.registry import (
    BUILTIN_CONTENT_DEFINITION_VERSION_ID,
    BUILTIN_RUNTIME_DEFAULTS,
)
from apps.api.database import build_session_factory, utc_now
from apps.api.errors import ApiError
from apps.api.identity.context import system_actor
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobService
from apps.api.lessons.domain import ApprovedLessonDivision, ApprovedLessonItem
from apps.api.lessons.service import LessonService
from apps.api.main import create_app
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import (
    ModelAuditContext,
    ModelCapability,
    TextModelRequest,
)
from apps.api.model_gateway.fake import DeterministicFakeTextProvider
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.prompt_runtime.service import PromptSnapshotService
from apps.api.reliability.models import OutboxEvent
from apps.api.reliability.outbox import OutboxDispatcher
from apps.api.reliability.sse import EventReplayRepository, parse_last_event_id
from apps.api.settings import Settings
from apps.api.uploads.confirmation_service import UploadConfirmationService
from apps.api.uploads.schemas import ConfirmUploadRequest, CreateUploadSessionRequest
from apps.api.uploads.session_service import UploadSessionService
from apps.api.workflows.service import WorkflowRuntimeService
from tests.conftest import run_migration
from tests.fakes.identity import configure_test_identity
from workers.material_parse import MaterialParseJobRunner
from workflow.node_state import NodeStatus
from workflow.prompt_runtime import (
    ContextBinding,
    ContextItem,
    PromptSection,
    assemble_context,
    compile_prompt,
)

pytestmark = pytest.mark.integration


def generated_pdf() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


def stage1_settings(database_url: str) -> Settings:
    settings = Settings(_env_file=None, environment="test", database_url=database_url)
    if not (
        settings.redis_url
        and settings.object_storage_endpoint
        and settings.object_storage_access_key
        and settings.object_storage_secret_key
    ):
        pytest.skip("stage1 E2E requires explicit PostgreSQL, Redis, and MinIO configuration")
    return settings


async def upload_in_chunks(url: str, payload: bytes) -> httpx.Response:
    async def chunks():
        midpoint = max(1, len(payload) // 2)
        yield payload[:midpoint]
        yield payload[midpoint:]

    async with httpx.AsyncClient(timeout=10) as client:
        return await client.put(
            url,
            content=chunks(),
            headers={
                "Content-Type": "application/pdf",
                "Content-Length": str(len(payload)),
            },
        )


def create_approved_artifact(
    session,
    actor,
    project_id: UUID,
    lesson_id: UUID,
    *,
    key: str,
    value: str,
):
    service = ArtifactService(session, actor)
    artifact = service.create(
        project_id,
        artifact_key=key,
        artifact_type="stage1_fixture",
        branch_key="lesson_plan",
        content_definition_version_id=BUILTIN_CONTENT_DEFINITION_VERSION_ID,
        lesson_unit_id=lesson_id,
        draft_branch="main",
        initial_content={"value": value},
        request_id=f"req-{key}-create",
    )
    draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
    assert draft is not None
    version = service.submit(
        artifact.id,
        "main",
        expected_lock_version=draft.lock_version,
        source_kind="manual",
        request_id=f"req-{key}-submit",
    )
    approval = service.review(
        version.id,
        action="approve",
        comment="Stage1 fixture approval",
        request_id=f"req-{key}-approve",
    )
    return artifact, version, approval


async def test_stage1_backend_vertical_flow_uses_real_services_and_fake_model(
    postgres_database_url: str,
    tmp_path: Path,
) -> None:
    run_migration(postgres_database_url, "head")
    settings = stage1_settings(postgres_database_url)
    app = create_app(settings=settings)
    actor = configure_test_identity(app)
    storage = app.state.object_storage
    assert storage is not None
    redis_client = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
    assert redis_client.ping() is True
    transport = httpx.ASGITransport(app=app)
    payload = generated_pdf()
    checksum = hashlib.sha256(payload).hexdigest()
    immutable_object: tuple[str, str] | None = None

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_headers = {"Idempotency-Key": "stage1-project-create"}
            project_payload = {"title": "Stage1 fractions", "knowledge_point": "One half"}
            created = await client.post(
                "/api/v2/projects", headers=project_headers, json=project_payload
            )
            replayed = await client.post(
                "/api/v2/projects", headers=project_headers, json=project_payload
            )
            conflict = await client.post(
                "/api/v2/projects",
                headers=project_headers,
                json={"title": "Conflicting title", "knowledge_point": "One half"},
            )
            assert created.status_code == 201
            assert replayed.json()["data"] == created.json()["data"]
            assert conflict.status_code == 409
            project = created.json()["data"]
            project_id = UUID(project["id"])
            assert project["content_release_id"] == str(BUILTIN_RUNTIME_DEFAULTS.content_release_id)
            assert project["workflow_definition_version_id"] == str(
                BUILTIN_RUNTIME_DEFAULTS.workflow_definition_version_id
            )

            upload_headers = {"Idempotency-Key": "stage1-upload-create"}
            upload_payload = {
                "filename": "generated-stage1.pdf",
                "media_type": "application/pdf",
                "size_bytes": len(payload),
                "sha256": checksum,
            }
            upload_response = await client.post(
                f"/api/v2/projects/{project_id}/materials/uploads",
                headers=upload_headers,
                json=upload_payload,
            )
            upload_replay = await client.post(
                f"/api/v2/projects/{project_id}/materials/uploads",
                headers=upload_headers,
                json=upload_payload,
            )
            assert upload_response.status_code == 201
            upload = upload_response.json()["data"]
            assert upload_replay.json()["data"] == upload
            uploaded = await upload_in_chunks(upload["upload_url"], payload)
            assert uploaded.status_code == 200, uploaded.text

            confirm_payload = {
                "upload_session_id": upload["upload_session_id"],
                "etag": uploaded.headers["ETag"].strip('"'),
                "size_bytes": len(payload),
                "sha256": checksum,
            }
            confirm_headers = {"Idempotency-Key": "stage1-upload-confirm"}
            confirmed = await client.post(
                f"/api/v2/projects/{project_id}/materials/{upload['material_id']}/confirm",
                headers=confirm_headers,
                json=confirm_payload,
            )
            confirm_replay = await client.post(
                f"/api/v2/projects/{project_id}/materials/{upload['material_id']}/confirm",
                headers=confirm_headers,
                json=confirm_payload,
            )
            assert confirmed.status_code == 202
            assert confirm_replay.json()["data"] == confirmed.json()["data"]
            job_id = UUID(confirmed.json()["data"]["job_id"])

        factory = build_session_factory(app.state.database_engine)
        worker = MaterialParseJobRunner(
            factory,
            storage=storage,
            parser=PypdfMaterialParser(),
            limits=settings_parse_limits(settings),
            settings=settings,
            temp_root=tmp_path,
        )

        def publish(event: OutboxEvent) -> None:
            assert redis_client.ping() is True
            if event.topic == "generation.job.queued" and event.aggregate_id == job_id:
                assert worker.run(job_id, worker_id="stage1-worker") == "succeeded"

        dispatcher = OutboxDispatcher(
            factory,
            worker_id="stage1-dispatcher",
            lease_seconds=settings.worker_lease_seconds,
            retry_seconds=settings.outbox_retry_seconds,
        )
        assert dispatcher.dispatch_batch(publish) >= 1
        assert worker.run(job_id, worker_id="stage1-worker-redelivery") == "ignored"

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            job_response = await client.get(f"/api/v2/generation-jobs/{job_id}")
            file_response = await client.get(
                f"/api/v2/projects/{project_id}/materials/{upload['material_id']}/file-asset"
            )
            parse_response = await client.get(
                f"/api/v2/projects/{project_id}/materials/{upload['material_id']}/parse-versions"
            )
        assert job_response.json()["data"]["status"] == "succeeded"
        file_version = file_response.json()["data"]["current_version"]
        assert file_version["sha256"] == checksum
        assert file_version["page_count"] == 2
        parses = parse_response.json()["data"]["items"]
        assert len(parses) == 1 and parses[0]["parser_name"] == "pypdf"

        with factory() as session, session.begin():
            persisted_version = session.get(FileAssetVersion, UUID(file_version["id"]))
            assert persisted_version is not None
            immutable_object = (persisted_version.storage_bucket, persisted_version.storage_key)
            lesson = LessonService(session, actor).synchronize_approved_division(
                project_id,
                ApprovedLessonDivision(
                    version_id=UUID(parses[0]["id"]),
                    lessons=(
                        ApprovedLessonItem(
                            lesson_key="lesson-01",
                            position=1,
                            title="Understanding one half",
                            scope_summary="Recognize equal parts.",
                            objective_summary="Explain one half.",
                            estimated_minutes=40,
                        ),
                    ),
                ),
                request_id="req-stage1-lessons",
            )[0]
            workflow_run = WorkflowRuntimeService(session, actor).start_project_run(project_id)
            node = WorkflowRuntimeService(session, actor).create_project_node_run(
                workflow_run.id, node_key="prepare", status=NodeStatus.READY
            )
            context = assemble_context(
                (
                    ContextBinding(
                        binding_key="project",
                        source="project.teacher_preferences",
                        required=True,
                        exposure="hidden",
                        max_items=1,
                        max_bytes=1_000,
                    ),
                ),
                {
                    "project.teacher_preferences": (
                        ContextItem(
                            source="project.teacher_preferences",
                            source_id=str(project_id),
                            source_version_id="1",
                            content={"knowledge_point": "One half"},
                        ),
                    )
                },
            )
            prompt = compile_prompt(
                template_key="stage1.text.smoke",
                template_version="1.0.0",
                platform_safety="PRIVATE_PLATFORM_POLICY",
                sections=(PromptSection("task", "task", "Return stage1 ok.", True, True),),
                context=context,
                output_schema={"type": "object"},
                provider_format="PRIVATE_PROVIDER_FORMAT",
            )
            frozen = PromptSnapshotService(session, actor).freeze(
                node.id, context=context, prompt=prompt
            )
            upstream, upstream_v1, _ = create_approved_artifact(
                session,
                actor,
                project_id,
                lesson.id,
                key="stage1-source",
                value="source-v1",
            )
            downstream, downstream_v1, approval = create_approved_artifact(
                session,
                actor,
                project_id,
                lesson.id,
                key="stage1-result",
                value="result-v1",
            )
            relation = ArtifactService(session, actor).add_relation(
                from_version_id=upstream_v1.id,
                to_version_id=downstream_v1.id,
                relation_type="derives_from",
                binding_key="source",
                impact_scope={"fields": ["value"]},
            )
            assert relation.id is not None and approval.id is not None
            slot = ProjectAssetService(session, actor).declare_slot(
                project_id,
                AssetSlotDeclaration(
                    slot_key="lesson.01.material.source",
                    lesson_unit_id=lesson.id,
                    asset_type="source_material",
                    cardinality=AssetCardinality.ONE,
                    required=True,
                    target_contract=AssetTargetContract(
                        allowed_mime_types=("application/pdf",), require_clean_scan=False
                    ),
                ),
                request_id="req-stage1-slot",
            )

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            preview = await client.get(f"/api/v2/node-runs/{node.id}/prompt-preview")
            binding_payload = {
                "file_asset_version_id": file_version["id"],
                "source_artifact_version_id": str(downstream_v1.id),
                "replace_mode": ReplaceMode.REJECT_IF_OCCUPIED.value,
                "position": None,
            }
            binding_headers = {"Idempotency-Key": "stage1-asset-bind"}
            bound = await client.post(
                f"/api/v2/asset-slots/{slot.id}/bindings",
                headers=binding_headers,
                json=binding_payload,
            )
            bound_replay = await client.post(
                f"/api/v2/asset-slots/{slot.id}/bindings",
                headers=binding_headers,
                json=binding_payload,
            )
        assert preview.status_code == 200
        assert preview.json()["data"]["prompt_snapshot_id"] == str(frozen.prompt.id)
        assert "PRIVATE_" not in preview.text
        assert bound.status_code == 201, bound.text
        assert bound_replay.json()["data"] == bound.json()["data"]

        gateway = ModelGateway(
            {ModelCapability.TEXT_SMOKE: DeterministicFakeTextProvider()},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        )
        model_result = await gateway.generate_text(
            TextModelRequest(
                capability=ModelCapability.TEXT_SMOKE,
                request_id="stage1-fake-model",
                prompt=prompt.compiled_prompt,
            ),
            audit_context=ModelAuditContext(
                organization_id=actor.organization_id,
                user_id=actor.user_id,
                project_id=project_id,
                node_run_id=node.id,
                generation_job_id=None,
            ),
        )
        assert model_result.text == "SHANHAIEDU_FAKE_SMOKE_OK"

        with factory() as session, session.begin():
            draft = ArtifactRepository(session, actor).get_draft(upstream.id, "main")
            assert draft is not None
            saved = ArtifactService(session, actor).save_draft(
                upstream.id,
                "main",
                expected_lock_version=draft.lock_version,
                content={"value": "source-v2"},
                request_id="req-stage1-source-save-v2",
            )
            upstream_v2 = ArtifactService(session, actor).submit(
                upstream.id,
                "main",
                expected_lock_version=saved.lock_version,
                source_kind="manual",
                request_id="req-stage1-source-submit-v2",
            )
            ArtifactService(session, actor).review(
                upstream_v2.id,
                action="approve",
                comment="Replace source",
                request_id="req-stage1-source-approve-v2",
            )

        with factory() as session:
            refreshed_downstream = session.get(Artifact, downstream.id)
            assert refreshed_downstream is not None and refreshed_downstream.status == "stale"
            assert session.scalar(select(func.count()).select_from(ArtifactRelation)) == 1
            assert session.scalar(select(func.count()).select_from(AssetBinding)) == 1
            assert session.scalar(select(func.count()).select_from(MaterialParseVersion)) == 1
            assert session.scalar(select(func.count()).select_from(GenerationAttempt)) == 1
            assert session.scalar(select(func.count()).select_from(UsageRecord)) == 1
            events = EventReplayRepository(session, actor.organization_id).replay(
                project_id=project_id,
                after_sequence=parse_last_event_id("0"),
                resource=("generation_job", job_id),
            )
            assert events[-1].summary_json["payload"]["status"] == "succeeded"
            resumed = EventReplayRepository(session, actor.organization_id).replay(
                project_id=project_id,
                after_sequence=parse_last_event_id(str(events[-2].sequence_no)),
                resource=("generation_job", job_id),
            )
            assert [event.sequence_no for event in resumed] == [events[-1].sequence_no]
            hidden = ProjectAssetService(
                session,
                replace(actor, organization_id=UUID("01990000-0000-7000-8000-000000000099")),
            )
            with pytest.raises(ApiError) as denied:
                hidden.bind(
                    slot.id,
                    file_asset_version_id=UUID(file_version["id"]),
                    source_artifact_version_id=downstream_v1.id,
                    replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
                    position=None,
                    request_id="req-stage1-cross-tenant",
                )
            assert denied.value.code == "ASSET_SLOT_NOT_FOUND"
    finally:
        redis_client.close()
        if immutable_object is not None:
            storage.delete(bucket=immutable_object[0], key=immutable_object[1])
        app.state.database_engine.dispose()


def settings_parse_limits(settings: Settings):
    from apps.api.assets.material_parser import ParseLimits

    return ParseLimits(
        max_pages=settings.material_parse_max_pages,
        max_text_chars=settings.material_parse_max_text_chars,
        max_text_blocks=settings.material_parse_max_text_blocks,
        max_image_references=settings.material_parse_max_image_references,
        timeout_seconds=settings.material_parse_timeout_seconds,
    )


def seed_real_material_job(
    factory,
    storage,
    actor,
    settings: Settings,
    *,
    suffix: str,
) -> UUID:
    payload = generated_pdf()
    checksum = hashlib.sha256(payload).hexdigest()
    with factory() as session:
        with session.begin():
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title=f"Worker {suffix}", knowledge_point="Recovery")
            )
        upload = UploadSessionService(
            session=session,
            storage=storage,
            actor=actor,
            bucket=settings.object_storage_bucket,
            ttl_seconds=settings.upload_session_ttl_seconds,
            max_size_bytes=settings.max_upload_size_bytes,
        ).create_session(
            project.id,
            CreateUploadSessionRequest(
                filename=f"{suffix}.pdf",
                media_type="application/pdf",
                size_bytes=len(payload),
                sha256=checksum,
            ),
            idempotency_key=f"stage1-{suffix}-upload",
            request_id=f"req-stage1-{suffix}-upload",
        )
        uploaded = httpx.put(
            str(upload.upload_url),
            content=payload,
            headers={"Content-Type": "application/pdf"},
            timeout=10,
        )
        assert uploaded.status_code == 200, uploaded.text
        accepted = UploadConfirmationService(
            session=session,
            storage=storage,
            actor=actor,
        ).confirm(
            project_id=project.id,
            material_id=upload.material_id,
            idempotency_key=f"stage1-{suffix}-confirm",
            payload=ConfirmUploadRequest(
                upload_session_id=upload.upload_session_id,
                etag=uploaded.headers["ETag"].strip('"'),
                size_bytes=len(payload),
                sha256=checksum,
            ),
            request_id=f"req-stage1-{suffix}-confirm",
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
        )
    return accepted.job_id


def test_cancel_and_expired_worker_lease_recover_without_duplicate_parse(
    postgres_database_url: str,
    tmp_path: Path,
) -> None:
    run_migration(postgres_database_url, "head")
    settings = stage1_settings(postgres_database_url)
    app = create_app(settings=settings)
    actor = configure_test_identity(app)
    storage = app.state.object_storage
    assert storage is not None
    factory = build_session_factory(app.state.database_engine)
    immutable_objects: list[tuple[str, str]] = []
    try:
        cancelled_job_id = seed_real_material_job(
            factory, storage, actor, settings, suffix="cancelled"
        )
        with factory() as session, session.begin():
            cancelled = GenerationJobService(
                session,
                actor=actor,
                idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
            ).request_cancel(
                cancelled_job_id,
                idempotency_key="stage1-cancel-job",
                request_id="req-stage1-cancel-job",
            )
            assert cancelled.status == "cancel_requested"

        worker = MaterialParseJobRunner(
            factory,
            storage=storage,
            parser=PypdfMaterialParser(),
            limits=settings_parse_limits(settings),
            settings=settings,
            temp_root=tmp_path,
        )
        assert worker.run(cancelled_job_id, worker_id="stage1-cancel-worker") == "ignored"

        recovered_job_id = seed_real_material_job(
            factory, storage, actor, settings, suffix="recovered"
        )
        with factory() as session, session.begin():
            claimed = GenerationJobService(
                session,
                actor=system_actor(actor.organization_id),
                idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
            ).claim(recovered_job_id, worker_id="stage1-stale-worker", lease_seconds=5)
            assert claimed is not None and claimed.status == "running"
            claimed.lease_expires_at = utc_now() - timedelta(seconds=1)

        assert worker.run(recovered_job_id, worker_id="stage1-recovery-worker") == "succeeded"
        assert worker.run(recovered_job_id, worker_id="stage1-redelivery-worker") == "ignored"

        with factory() as session:
            cancelled = session.get(GenerationJob, cancelled_job_id)
            recovered = session.get(GenerationJob, recovered_job_id)
            assert cancelled is not None and cancelled.status == "cancelled"
            assert cancelled.attempt_count == 0
            assert recovered is not None and recovered.status == "succeeded"
            assert recovered.attempt_count == 2
            assert session.scalar(select(func.count()).select_from(MaterialParseVersion)) == 1
            immutable_objects = list(
                session.execute(
                    select(FileAssetVersion.storage_bucket, FileAssetVersion.storage_key)
                ).tuples()
            )
    finally:
        for bucket, key in immutable_objects:
            storage.delete(bucket=bucket, key=key)
        app.state.database_engine.dispose()


def test_redis_restart_leaves_postgres_outbox_recoverable(
    postgres_database_url: str,
) -> None:
    if os.environ.get("SHANHAI_E2E_ALLOW_SERVICE_RESTART") != "1":
        pytest.skip("set SHANHAI_E2E_ALLOW_SERVICE_RESTART=1 for the controlled Redis restart")
    run_migration(postgres_database_url, "head")
    settings = stage1_settings(postgres_database_url)
    app = create_app(settings=settings)
    actor = configure_test_identity(app)
    factory = build_session_factory(app.state.database_engine)
    redis_client = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
    compose = ["docker", "compose", "-f", "infra/compose.yaml"]
    try:
        with factory() as session, session.begin():
            from apps.api.reliability.events import EventResource, EventWriter

            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Redis recovery", knowledge_point="Durable outbox")
            )
            EventWriter(session, actor.organization_id).append(
                project_id=project.id,
                event_type="stage1.redis.recovery",
                resource=EventResource(type="project", id=project.id),
                payload={"status": "queued"},
                request_id="req-stage1-redis-recovery",
            )

        subprocess.run([*compose, "stop", "redis"], check=True, timeout=30)
        with pytest.raises(RedisError):
            redis_client.ping()
        dispatcher = OutboxDispatcher(
            factory,
            worker_id="stage1-redis-outage",
            lease_seconds=5,
            retry_seconds=1,
        )
        assert dispatcher.dispatch_batch(lambda _: redis_client.ping()) == 0

        subprocess.run([*compose, "start", "redis"], check=True, timeout=30)
        deadline = time.monotonic() + 30
        while True:
            try:
                if redis_client.ping():
                    break
            except RedisError:
                pass
            if time.monotonic() >= deadline:
                raise AssertionError("Redis did not recover within 30 seconds")
            time.sleep(0.25)
        time.sleep(1.1)
        assert dispatcher.dispatch_batch(lambda _: redis_client.ping()) >= 1
        with factory() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(OutboxEvent)
                    .where(OutboxEvent.status == "pending")
                )
                == 0
            )
    finally:
        subprocess.run([*compose, "start", "redis"], check=False, timeout=30)
        redis_client.close()
        app.state.database_engine.dispose()
