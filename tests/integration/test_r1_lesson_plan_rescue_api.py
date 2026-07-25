from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import httpx
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.artifacts.models import Artifact
from apps.api.database import build_engine, build_session_factory
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonUnit
from apps.api.main import create_app
from apps.api.settings import Settings
from tests.fakes.identity import override_test_identity, seed_test_actor
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.test_lesson_plan_runtime import (
    _prepare_generated_lesson_plan,  # pyright: ignore[reportPrivateUsage]
)
from workers.artifact_quality import execute_artifact_quality_node


async def test_exact_lesson_plan_api_restores_edit_quality_approval_and_tenant_scope(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    prepared = await _prepare_generated_lesson_plan(factory)
    with factory() as session:
        artifact = session.get(Artifact, prepared.artifact_id)
        assert artifact is not None and artifact.lesson_unit_id is not None
        project_id = artifact.project_id
        lesson_unit_id = artifact.lesson_unit_id
        lesson = session.get(LessonUnit, lesson_unit_id)
        assert lesson is not None and lesson.project_id == project_id

    settings = Settings(
        environment="test",
        database_url=SecretStr(migrated_database_url),
    )
    app = create_app(settings=settings, object_storage=FakeObjectStorage())
    override_test_identity(app, prepared.actor)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            initial = await _get_lesson_plan(client, project_id, lesson_unit_id)
            initial_artifact = cast(dict[str, Any], initial["artifact"])
            initial_draft = cast(dict[str, Any], initial_artifact["current_draft"])
            assert initial_artifact["id"] == str(prepared.artifact_id)
            assert initial_draft["based_on_version_id"] == str(prepared.version_id)
            assert initial["quality_report"] is None

            edited = deepcopy(cast(dict[str, Any], initial_draft["content"]))
            teaching_content = cast(dict[str, Any], edited["teaching_content"])
            teaching_content["lesson_topic"] = "教师保存的十二部分教案"
            draft_lock = cast(int, initial_draft["lock_version"])
            saved = await client.put(
                f"/api/v2/artifacts/{prepared.artifact_id}/drafts/main",
                headers={
                    "Idempotency-Key": "r1-rescue-save-edited-plan",
                    "If-Match": f'W/"{draft_lock}"',
                },
                json={"content": edited},
            )
            assert saved.status_code == 200, saved.text
            saved_draft = saved.json()["data"]
            assert saved_draft["content"] == edited

            submitted = await client.post(
                f"/api/v2/artifacts/{prepared.artifact_id}/versions",
                headers={
                    "Idempotency-Key": "r1-rescue-submit-edited-plan",
                    "If-Match": f'W/"{saved_draft["lock_version"]}"',
                },
                json={"draft_branch": "main"},
            )
            assert submitted.status_code == 201, submitted.text
            submitted_version_id = UUID(submitted.json()["data"]["id"])
            assert submitted_version_id != prepared.version_id

            quality = await client.post(
                "/api/v2/lessons/"
                f"{lesson_unit_id}/lesson-plan/artifact-versions/"
                f"{submitted_version_id}/quality-validations",
                headers={"Idempotency-Key": "r1-rescue-quality-edited-plan"},
            )
            assert quality.status_code == 202, quality.text
            quality_node_id = UUID(quality.json()["data"]["node_run_id"])
            report = execute_artifact_quality_node(
                migrated_database_url,
                quality_node_id,
                runtime_quality_validator_registry(),
            )
            assert report is not None and report.conclusion == "passed"

            wrong_version = await client.post(
                f"/api/v2/artifact-versions/{prepared.version_id}/approvals",
                headers={"Idempotency-Key": "r1-rescue-reject-old-version"},
                json={"action": "approve", "comment": "Must not approve the old version."},
            )
            assert wrong_version.status_code == 409, wrong_version.text

            approved = await client.post(
                f"/api/v2/artifact-versions/{submitted_version_id}/approvals",
                headers={"Idempotency-Key": "r1-rescue-approve-exact-version"},
                json={"action": "approve", "comment": "Approve the exact edited version."},
            )
            assert approved.status_code == 201, approved.text
            assert approved.json()["data"]["artifact_version_id"] == str(submitted_version_id)

            restored = await _get_lesson_plan(client, project_id, lesson_unit_id)
            restored_artifact = cast(dict[str, Any], restored["artifact"])
            restored_version = cast(
                dict[str, Any],
                restored_artifact["current_approved_version"],
            )
            restored_report = cast(dict[str, Any], restored["quality_report"])
            restored_approval = cast(dict[str, Any], restored["latest_approval"])
            assert restored_artifact["status"] == "approved"
            assert restored_version["id"] == str(submitted_version_id)
            assert restored_report["artifact_version_id"] == str(submitted_version_id)
            assert restored_report["conclusion"] == "passed"
            assert restored_approval["action"] == "approve"
            assert restored_approval["artifact_version_id"] == str(submitted_version_id)

            foreign_actor = _seed_foreign_actor(factory)
            override_test_identity(app, foreign_actor)
            cross_tenant = await client.get(
                f"/api/v2/projects/{project_id}/lessons/{lesson_unit_id}/lesson-plan/artifact"
            )
            assert cross_tenant.status_code == 404, cross_tenant.text
    finally:
        app.state.database_engine.dispose()
        engine.dispose()


async def _get_lesson_plan(
    client: httpx.AsyncClient,
    project_id: UUID,
    lesson_unit_id: UUID,
) -> dict[str, Any]:
    response = await client.get(
        f"/api/v2/projects/{project_id}/lessons/{lesson_unit_id}/lesson-plan/artifact"
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _seed_foreign_actor(factory: sessionmaker[Session]):
    organization_id = new_uuid7()
    with factory() as session, session.begin():
        session.add(
            Organization(
                id=organization_id,
                slug=f"r1-rescue-{organization_id.hex[:12]}",
                name="R1 rescue foreign tenant",
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        session.flush()
        return seed_test_actor(
            session,
            organization_id=organization_id,
            user_id=new_uuid7(),
            principal_id=new_uuid7(),
            member_id=new_uuid7(),
            email=f"r1-rescue-{organization_id.hex[:12]}@example.test",
            display_name="R1 rescue foreign teacher",
        )
