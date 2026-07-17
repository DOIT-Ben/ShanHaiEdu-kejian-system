from __future__ import annotations

from uuid import UUID

import httpx

from apps.api.database import build_session_factory
from apps.api.lessons.domain import ApprovedLessonDivision, ApprovedLessonItem
from apps.api.lessons.service import LessonService
from apps.api.main import create_app
from apps.api.settings import Settings
from tests.conftest import run_migration
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.identity import configure_test_identity

DIVISION_VERSION = UUID("01930000-0000-7000-8000-000000000001")
DIVISION_VERSION_TWO = UUID("01930000-0000-7000-8000-000000000002")


async def test_lesson_reads_and_idempotent_branch_updates_use_etags(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
        )
    )
    actor = configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "lesson-project-create-001"},
                json={"title": "Fractions", "knowledge_point": "One half"},
            )
            assert created.status_code == 201
            project_id = UUID(created.json()["data"]["id"])

            factory = build_session_factory(app.state.database_engine)
            with factory() as session, session.begin():
                lesson = LessonService(session, actor).synchronize_approved_division(
                    project_id,
                    ApprovedLessonDivision(
                        version_id=DIVISION_VERSION,
                        lessons=(
                            ApprovedLessonItem(
                                lesson_key="lesson-01",
                                position=1,
                                title="What is one half?",
                                scope_summary="Recognize one half",
                                objective_summary="Represent one half",
                                estimated_minutes=40,
                            ),
                        ),
                    ),
                    request_id="req_fixture_sync",
                )[0]

            listing = await client.get(f"/api/v2/projects/{project_id}/lessons")
            detail = await client.get(f"/api/v2/lessons/{lesson.id}")
            assert listing.status_code == 200, listing.text
            assert_contract_response(listing, operation_id="listProjectLessons", status="200")
            assert listing.headers["ETag"] == 'W/"2"'
            assert [item["id"] for item in listing.json()["data"]["items"]] == [str(lesson.id)]
            assert detail.status_code == 200, detail.text
            assert_contract_response(detail, operation_id="getLesson", status="200")
            assert detail.headers["ETag"] == 'W/"1"'

            headers = {
                "Idempotency-Key": "lesson-branches-update-001",
                "If-Match": 'W/"1"',
            }
            payload = {
                "branches": [{"branch_key": "ppt", "enabled": True, "settings": {"ratio": "16:9"}}]
            }
            updated = await client.patch(
                f"/api/v2/lessons/{lesson.id}/branches",
                headers=headers,
                json=payload,
            )
            replay = await client.patch(
                f"/api/v2/lessons/{lesson.id}/branches",
                headers=headers,
                json=payload,
            )
            assert updated.status_code == 200, updated.text
            assert_contract_response(updated, operation_id="updateLessonBranches", status="200")
            assert updated.headers["ETag"] == 'W/"2"'
            assert replay.status_code == 200, replay.text
            assert replay.json()["data"] == updated.json()["data"]

            stale = await client.patch(
                f"/api/v2/lessons/{lesson.id}/branches",
                headers={
                    "Idempotency-Key": "lesson-branches-update-002",
                    "If-Match": 'W/"1"',
                },
                json={"branches": [{"branch_key": "video", "enabled": True, "settings": {}}]},
            )
            assert stale.status_code == 409
            assert stale.json()["error"]["code"] == "EDIT_CONFLICT"

            conflict = await client.patch(
                f"/api/v2/lessons/{lesson.id}/branches",
                headers=headers,
                json={"branches": [{"branch_key": "video", "enabled": True, "settings": {}}]},
            )
            assert conflict.status_code == 409
            assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

            required = await client.patch(
                f"/api/v2/lessons/{lesson.id}/branches",
                headers={
                    "Idempotency-Key": "lesson-branches-update-003",
                    "If-Match": 'W/"2"',
                },
                json={
                    "branches": [{"branch_key": "lesson_plan", "enabled": False, "settings": {}}]
                },
            )
            assert required.status_code == 422
            assert required.json()["error"]["code"] == "LESSON_PLAN_REQUIRED"
    finally:
        app.state.database_engine.dispose()


async def test_lesson_collection_patch_reorders_updates_archives_and_replays(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
        )
    )
    actor = configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "lesson-collection-project-001"},
                json={"title": "Fractions", "knowledge_point": "One half"},
            )
            project_id = UUID(created.json()["data"]["id"])
            factory = build_session_factory(app.state.database_engine)
            with factory() as session, session.begin():
                lessons = LessonService(session, actor).synchronize_approved_division(
                    project_id,
                    ApprovedLessonDivision(
                        version_id=DIVISION_VERSION_TWO,
                        lessons=(
                            ApprovedLessonItem(
                                lesson_key="lesson-01",
                                position=1,
                                title="First",
                                scope_summary="First scope",
                                objective_summary="First objective",
                                estimated_minutes=40,
                            ),
                            ApprovedLessonItem(
                                lesson_key="lesson-02",
                                position=2,
                                title="Second",
                                scope_summary="Second scope",
                                objective_summary="Second objective",
                                estimated_minutes=40,
                            ),
                        ),
                    ),
                    request_id="req_collection_sync",
                )
            first, second = lessons

            headers = {
                "Idempotency-Key": "lesson-collection-update-001",
                "If-Match": 'W/"2"',
            }
            payload = {
                "items": [
                    {
                        "id": str(second.id),
                        "position": 1,
                        "title": "Second revised",
                        "scope_summary": "Revised scope",
                        "objective_summary": "Revised objective",
                        "estimated_minutes": 45,
                    }
                ]
            }
            updated = await client.patch(
                f"/api/v2/projects/{project_id}/lessons",
                headers=headers,
                json=payload,
            )
            replay = await client.patch(
                f"/api/v2/projects/{project_id}/lessons",
                headers=headers,
                json=payload,
            )
            archived = await client.get(f"/api/v2/lessons/{first.id}")

            assert updated.status_code == 200, updated.text
            assert_contract_response(updated, operation_id="updateProjectLessons", status="200")
            assert updated.headers["ETag"] == 'W/"3"'
            assert replay.status_code == 200, replay.text
            assert replay.json()["data"] == updated.json()["data"]
            assert updated.json()["data"]["items"][0]["id"] == str(second.id)
            assert updated.json()["data"]["items"][0]["title"] == "Second revised"
            assert archived.status_code == 200
            assert archived.json()["data"]["status"] == "archived"
            assert archived.json()["data"]["position"] == 2

            stale = await client.patch(
                f"/api/v2/projects/{project_id}/lessons",
                headers={
                    "Idempotency-Key": "lesson-collection-update-002",
                    "If-Match": 'W/"2"',
                },
                json=payload,
            )
            assert stale.status_code == 409
            assert stale.json()["error"]["code"] == "EDIT_CONFLICT"
    finally:
        app.state.database_engine.dispose()
