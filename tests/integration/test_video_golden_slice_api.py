from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select

from apps.api.assets.project_contracts import (
    AssetCardinality,
    AssetSlotDeclaration,
    AssetTargetContract,
    ReplaceMode,
)
from apps.api.assets.project_service import ProjectAssetService
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.main import create_app
from apps.api.projects.models import Project
from apps.api.settings import Settings
from apps.api.workflows.models import WorkflowDefinitionVersion, WorkflowRun
from tests.conftest import run_migration
from tests.fakes.identity import override_test_identity
from tests.integration.identity_session_support import APP_ORIGIN, login, runtime_settings
from tests.integration.test_project_asset_bindings import (
    seed_file_version,  # pyright: ignore[reportUnknownVariableType]
)
from tests.integration.video_golden_slice_support import seed_video_project


def _start_path(project_id: UUID, lesson_id: UUID) -> str:
    return f"/api/v2/projects/{project_id}/lessons/{lesson_id}/video/generations"


def _start_payload(keyframe_file_version_id: UUID) -> dict[str, str]:
    return {"keyframe_file_asset_version_id": str(keyframe_file_version_id)}


async def test_video_start_freezes_exact_inputs_and_isolates_two_lessons(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    engine = build_engine(postgres_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory)
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
            session_access_code=None,
            session_allowed_origins=[],
            session_csrf_secret=None,
            session_teacher_principal_id=None,
        ),
        session_factory=factory,
    )
    override_test_identity(app, seeded.actor)
    first, second = seeded.lessons
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            first_start = await client.post(
                _start_path(seeded.project_id, first.lesson_id),
                headers={"Idempotency-Key": "video-first-start"},
                json=_start_payload(first.keyframe_file_version_id),
            )
            first_replay = await client.post(
                _start_path(seeded.project_id, first.lesson_id),
                headers={"Idempotency-Key": "video-first-start"},
                json=_start_payload(first.keyframe_file_version_id),
            )
            duplicate = await client.post(
                _start_path(seeded.project_id, first.lesson_id),
                headers={"Idempotency-Key": "video-first-duplicate"},
                json=_start_payload(first.keyframe_file_version_id),
            )
            wrong_lesson_keyframe = await client.post(
                _start_path(seeded.project_id, first.lesson_id),
                headers={"Idempotency-Key": "video-first-wrong-lesson"},
                json=_start_payload(second.keyframe_file_version_id),
            )
            second_start = await client.post(
                _start_path(seeded.project_id, second.lesson_id),
                headers={"Idempotency-Key": "video-second-start"},
                json=_start_payload(second.keyframe_file_version_id),
            )
        assert first_start.status_code == 202, first_start.text
        assert first_replay.status_code == 202, first_replay.text
        assert first_replay.json()["data"] == first_start.json()["data"]
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "VIDEO_GENERATION_ALREADY_ACTIVE"
        assert wrong_lesson_keyframe.status_code == 409
        assert wrong_lesson_keyframe.json()["error"]["code"] == "VIDEO_KEYFRAME_INVALID"
        assert second_start.status_code == 202, second_start.text
        assert second_start.json()["data"]["job_id"] != first_start.json()["data"]["job_id"]
        with factory() as session:
            jobs = list(
                session.scalars(
                    select(GenerationJob)
                    .where(
                        GenerationJob.project_id == seeded.project_id,
                        GenerationJob.workflow_node_key == "video.shots.generate",
                    )
                    .order_by(GenerationJob.lesson_unit_id)
                )
            )
        assert len(jobs) == 2
        frozen_by_lesson = {job.lesson_unit_id: job.creation_request_json for job in jobs}
        assert frozen_by_lesson[first.lesson_id] == {
            "intro_selection_id": str(first.intro_selection_id),
            "intro_artifact_version_id": str(first.intro_artifact_version_id),
            "keyframe_file_version_id": str(first.keyframe_file_version_id),
            "keyframe_slot_key": first.keyframe_slot_key,
        }
        assert frozen_by_lesson[second.lesson_id] == {
            "intro_selection_id": str(second.intro_selection_id),
            "intro_artifact_version_id": str(second.intro_artifact_version_id),
            "keyframe_file_version_id": str(second.keyframe_file_version_id),
            "keyframe_slot_key": second.keyframe_slot_key,
        }
    finally:
        engine.dispose()


async def test_video_start_hides_cross_tenant_keyframes(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    engine = build_engine(postgres_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    with factory() as session, session.begin():
        foreign_organization_id = new_uuid7()
        session.add(
            Organization(
                id=foreign_organization_id,
                slug=f"video-foreign-{foreign_organization_id.hex[:8]}",
                name="Video foreign organization",
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        foreign_keyframe = seed_file_version(
            session,
            seeded.actor,
            organization_id=foreign_organization_id,
        )
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
            session_access_code=None,
            session_allowed_origins=[],
            session_csrf_secret=None,
            session_teacher_principal_id=None,
        ),
        session_factory=factory,
    )
    override_test_identity(app, seeded.actor)
    lesson = seeded.lessons[0]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                _start_path(seeded.project_id, lesson.lesson_id),
                headers={"Idempotency-Key": "video-cross-tenant"},
                json=_start_payload(foreign_keyframe.id),
            )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "VIDEO_KEYFRAME_NOT_FOUND"
    finally:
        engine.dispose()


async def test_video_start_rejects_image_from_non_keyframe_lesson_slot(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    engine = build_engine(postgres_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    lesson = seeded.lessons[0]
    with factory() as session, session.begin():
        version = seed_file_version(session, seeded.actor)
        assets = ProjectAssetService(session, seeded.actor)
        slot = assets.declare_slot(
            seeded.project_id,
            AssetSlotDeclaration(
                slot_key="lesson.01.ppt.page.01.main_visual",
                lesson_unit_id=lesson.lesson_id,
                asset_type="image",
                cardinality=AssetCardinality.ONE,
                required=True,
                target_contract=AssetTargetContract(
                    allowed_mime_types=("image/png",),
                    require_clean_scan=True,
                ),
            ),
            request_id="video-wrong-slot-declare",
        )
        assets.bind(
            slot.id,
            file_asset_version_id=version.id,
            source_artifact_version_id=None,
            replace_mode=ReplaceMode.REJECT_IF_OCCUPIED,
            position=None,
            request_id="video-wrong-slot-bind",
        )
        wrong_version_id = version.id
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
            session_access_code=None,
            session_allowed_origins=[],
            session_csrf_secret=None,
            session_teacher_principal_id=None,
        ),
        session_factory=factory,
    )
    override_test_identity(app, seeded.actor)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                _start_path(seeded.project_id, lesson.lesson_id),
                headers={"Idempotency-Key": "video-wrong-slot-start"},
                json=_start_payload(wrong_version_id),
            )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "VIDEO_KEYFRAME_INVALID"
    finally:
        engine.dispose()


async def test_video_start_requires_the_project_published_golden_slice_contract(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    engine = build_engine(postgres_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    with factory() as session, session.begin():
        run = session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.project_id == seeded.project_id,
                WorkflowRun.status == "active",
            )
        )
        workflow = session.get(
            WorkflowDefinitionVersion,
            run.workflow_definition_version_id if run is not None else None,
        )
        assert workflow is not None
        graph = deepcopy(workflow.graph_json)
        node = next(item for item in graph["nodes"] if item["node_key"] == "video.shots.generate")
        node["entrypoint"] = False
        node["dependencies"] = ["video.fine_storyboard.generate"]
        node["input_contract_refs"] = [
            "artifact:video_fine_storyboard",
            "contract:video_style",
        ]
        legacy_workflow = WorkflowDefinitionVersion(
            id=new_uuid7(),
            workflow_definition_id=workflow.workflow_definition_id,
            version_no=workflow.version_no + 1,
            graph_json=graph,
            input_contract_json=deepcopy(workflow.input_contract_json),
            status="published",
            checksum="f" * 64,
            published_at=datetime.now(UTC),
        )
        session.add(legacy_workflow)
        session.flush()
        run.workflow_definition_version_id = legacy_workflow.id
        project = session.get(Project, seeded.project_id)
        assert project is not None
        project.workflow_definition_version_id = legacy_workflow.id

    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
            session_access_code=None,
            session_allowed_origins=[],
            session_csrf_secret=None,
            session_teacher_principal_id=None,
        ),
        session_factory=factory,
    )
    override_test_identity(app, seeded.actor)
    lesson = seeded.lessons[0]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                _start_path(seeded.project_id, lesson.lesson_id),
                headers={"Idempotency-Key": "video-old-workflow-contract"},
                json=_start_payload(lesson.keyframe_file_version_id),
            )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "VIDEO_LESSON_NOT_FOUND"
    finally:
        engine.dispose()


async def test_video_start_requires_session_csrf_and_logout_invalidates_write(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    engine = build_engine(postgres_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    settings = runtime_settings(
        postgres_database_url,
        access_code="video-access-code-01234567",
        csrf_secret="video-csrf-placeholder-0123456789abcdef",
    )
    app = create_app(settings=settings, session_factory=factory)
    lesson = seeded.lessons[0]
    path = _start_path(seeded.project_id, lesson.lesson_id)
    payload = _start_payload(lesson.keyframe_file_version_id)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 50421)),
            base_url=APP_ORIGIN,
        ) as client:
            anonymous = await client.post(
                path,
                headers={"Idempotency-Key": "video-auth-anonymous"},
                json=payload,
            )
            created = await login(client, "video-access-code-01234567")
            assert created.status_code == 201, created.text
            csrf_token = created.json()["data"]["csrf_token"]
            missing_csrf = await client.post(
                path,
                headers={
                    "Idempotency-Key": "video-auth-no-csrf",
                    "Origin": APP_ORIGIN,
                },
                json=payload,
            )
            logout = await client.delete(
                "/api/v2/auth/session",
                headers={"Origin": APP_ORIGIN, "X-CSRF-Token": csrf_token},
            )
            after_logout = await client.post(
                path,
                headers={
                    "Idempotency-Key": "video-auth-after-logout",
                    "Origin": APP_ORIGIN,
                    "X-CSRF-Token": csrf_token,
                },
                json=payload,
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
