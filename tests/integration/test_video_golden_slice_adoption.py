from __future__ import annotations

import httpx
from sqlalchemy import select

from apps.api.assets.project_models import AssetBinding, ProjectAssetSlot
from apps.api.creation.models import Adoption
from apps.api.database import build_engine, build_session_factory
from apps.api.main import create_app
from apps.api.settings import Settings
from tests.conftest import run_migration
from tests.fakes.identity import override_test_identity
from tests.integration.video_golden_slice_support import (
    seed_completed_candidate,
    seed_video_project,
)


async def test_exact_video_result_adoption_cannot_cross_lesson_and_saves_exact_slot(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    engine = build_engine(postgres_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory)
    with factory() as session, session.begin():
        first_candidate = seed_completed_candidate(session, seeded, lesson_index=0)
        second_candidate = seed_completed_candidate(session, seeded, lesson_index=1)
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
    first_adopt_path = (
        f"/api/v2/projects/{seeded.project_id}/lessons/{first.lesson_id}"
        f"/video/results/{first_candidate.result_id}/adoptions"
    )
    wrong_adopt_path = (
        f"/api/v2/projects/{seeded.project_id}/lessons/{first.lesson_id}"
        f"/video/results/{second_candidate.result_id}/adoptions"
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            wrong = await client.post(
                wrong_adopt_path,
                headers={"Idempotency-Key": "video-adopt-wrong-result"},
                json={"reason": "This result belongs to another lesson."},
            )
            adopted = await client.post(
                first_adopt_path,
                headers={"Idempotency-Key": "video-adopt-first-result"},
                json={"reason": "Use this exact classroom intro clip."},
            )
            assert adopted.status_code == 201, adopted.text
            adoption_id = adopted.json()["data"]["id"]
            save_path = (
                f"/api/v2/projects/{seeded.project_id}/lessons/{first.lesson_id}"
                f"/video/adoptions/{adoption_id}/save"
            )
            saved = await client.post(
                save_path,
                headers={"Idempotency-Key": "video-save-first-result"},
                json={"replace_mode": "replace_active"},
            )
            replay = await client.post(
                save_path,
                headers={"Idempotency-Key": "video-save-first-result"},
                json={"replace_mode": "replace_active"},
            )
        assert wrong.status_code == 404
        assert wrong.json()["error"]["code"] == "VIDEO_RESULT_NOT_FOUND"
        assert saved.status_code == 200, saved.text
        assert replay.status_code == 200, replay.text
        assert replay.json()["data"] == saved.json()["data"]
        with factory() as session:
            adoption = session.get(Adoption, adopted.json()["data"]["id"])
            first_slot = session.scalar(
                select(ProjectAssetSlot).where(
                    ProjectAssetSlot.project_id == seeded.project_id,
                    ProjectAssetSlot.lesson_unit_id == first.lesson_id,
                    ProjectAssetSlot.slot_key == first_candidate.target_slot_key,
                )
            )
            second_slot = session.scalar(
                select(ProjectAssetSlot).where(
                    ProjectAssetSlot.project_id == seeded.project_id,
                    ProjectAssetSlot.lesson_unit_id == second.lesson_id,
                    ProjectAssetSlot.slot_key == second_candidate.target_slot_key,
                )
            )
            first_binding = session.scalar(
                select(AssetBinding).where(
                    AssetBinding.project_asset_slot_id == first_slot.id,
                    AssetBinding.is_active.is_(True),
                )
            )
            second_binding_count = len(
                list(
                    session.scalars(
                        select(AssetBinding).where(
                            AssetBinding.project_asset_slot_id == second_slot.id,
                            AssetBinding.is_active.is_(True),
                        )
                    )
                )
            )
        assert adoption is not None
        assert adoption.generation_result_id == first_candidate.result_id
        assert first_binding is not None
        assert first_binding.file_asset_version_id == first_candidate.file_asset_version_id
        assert first_binding.source_generation_result_id == first_candidate.result_id
        assert second_binding_count == 0
    finally:
        engine.dispose()


async def test_video_adoption_rejects_same_lesson_result_with_invalid_file_facts(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    engine = build_engine(postgres_database_url)
    factory = build_session_factory(engine)
    seeded = await seed_video_project(factory, lesson_count=1)
    with factory() as session, session.begin():
        candidate = seed_completed_candidate(
            session,
            seeded,
            lesson_index=0,
            mime_type="image/png",
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
                f"/api/v2/projects/{seeded.project_id}/lessons/{lesson.lesson_id}"
                f"/video/results/{candidate.result_id}/adoptions",
                headers={"Idempotency-Key": "video-adopt-invalid-file"},
                json={"reason": "This invalid file must not be adopted."},
            )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "VIDEO_RESULT_NOT_FOUND"
    finally:
        engine.dispose()
