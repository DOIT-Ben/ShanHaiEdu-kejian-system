from __future__ import annotations

from uuid import UUID

import httpx

from apps.api.database import build_session_factory
from apps.api.main import create_app
from apps.api.settings import Settings
from tests.conftest import run_migration
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.content_runtime import ensure_test_authoring_definition
from tests.fakes.identity import configure_test_identity


async def test_artifact_draft_submit_and_approval_api_matches_contract(
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
    configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            project_response = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "artifact-project-001"},
                json={
                    "title": "Fractions",
                    "knowledge_point": "Understanding one half",
                },
            )
            project_id = project_response.json()["data"]["id"]
            factory = build_session_factory(app.state.database_engine)
            with factory() as session, session.begin():
                definition_id = ensure_test_authoring_definition(session, UUID(project_id))

            created = await client.post(
                f"/api/v2/projects/{project_id}/artifacts",
                headers={"Idempotency-Key": "artifact-create-001"},
                json={
                    "artifact_key": "lesson-plan:lesson-01",
                    "artifact_type": "lesson_plan",
                    "branch_key": "lesson_plan",
                    "content_definition_version_id": str(definition_id),
                    "draft_branch": "main",
                    "content": {"title": "Draft"},
                },
            )
            assert created.status_code == 201, created.text
            assert_contract_response(created, operation_id="createArtifact", status="201")
            artifact_id = created.json()["data"]["id"]

            detail = await client.get(f"/api/v2/artifacts/{artifact_id}")
            assert detail.status_code == 200, detail.text
            assert detail.headers["ETag"] == 'W/"1"'
            assert_contract_response(detail, operation_id="getArtifact", status="200")

            saved = await client.put(
                f"/api/v2/artifacts/{artifact_id}/drafts/main",
                headers={
                    "If-Match": detail.headers["ETag"],
                    "Idempotency-Key": "artifact-save-001",
                },
                json={"content": {"title": "Ready for review"}},
            )
            assert saved.status_code == 200, saved.text
            assert saved.headers["ETag"] == 'W/"2"'
            assert_contract_response(saved, operation_id="saveArtifactDraft", status="200")

            submitted = await client.post(
                f"/api/v2/artifacts/{artifact_id}/versions",
                headers={
                    "If-Match": saved.headers["ETag"],
                    "Idempotency-Key": "artifact-submit-001",
                },
                json={"draft_branch": "main"},
            )
            assert submitted.status_code == 201, submitted.text
            assert_contract_response(submitted, operation_id="submitArtifactVersion", status="201")
            version_id = submitted.json()["data"]["id"]

            approved = await client.post(
                f"/api/v2/artifact-versions/{version_id}/approvals",
                headers={"Idempotency-Key": "artifact-approve-001"},
                json={"action": "approve", "comment": "Ready"},
            )
            assert approved.status_code == 201, approved.text
            assert_contract_response(approved, operation_id="reviewArtifactVersion", status="201")

            final = await client.get(f"/api/v2/artifacts/{artifact_id}")
            assert final.json()["data"]["status"] == "approved"
            assert final.json()["data"]["current_approved_version"]["id"] == version_id
    finally:
        app.state.database_engine.dispose()
