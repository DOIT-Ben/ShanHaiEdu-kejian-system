from __future__ import annotations

from uuid import UUID

import httpx

from apps.api.creation.models import GenerationResult
from apps.api.database import build_session_factory, utc_now
from apps.api.ids import new_uuid7
from apps.api.main import create_app
from apps.api.projects.models import Project
from apps.api.settings import Settings
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.identity import configure_test_identity
from tests.integration.test_creation_lifecycle import (
    declare_target_slot,
    seed_project_package,
)
from tests.integration.test_project_asset_bindings import seed_file_version


async def test_creation_http_flow_matches_the_shared_contract(
    migrated_database_url: str,
) -> None:
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=migrated_database_url,
        )
    )
    actor = configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "creation-api-project-001"},
                json={
                    "title": "Fractions",
                    "knowledge_point": "One half",
                    "execution_mode": "automatic",
                },
            )
            assert created.status_code == 201, created.text
            assert_contract_response(created, operation_id="createProject", status="201")
            created_project = created.json()["data"]
            assert created_project["execution_mode"] == "automatic"
            assert "automation_mode" not in created_project
            project_id = UUID(created_project["id"])

            initial_project = await client.get(f"/api/v2/projects/{project_id}")
            assert initial_project.status_code == 200, initial_project.text
            assert_contract_response(initial_project, operation_id="getProject", status="200")
            initial_project_etag = initial_project.headers["ETag"]

            policy = await client.get(f"/api/v2/projects/{project_id}/automation-policy")
            assert policy.status_code == 200, policy.text
            assert_contract_response(
                policy,
                operation_id="getProjectAutomationPolicy",
                status="200",
            )
            assert policy.json()["data"]["mode"] == "automatic"
            changed_policy = await client.patch(
                f"/api/v2/projects/{project_id}/automation-policy",
                headers={
                    "Idempotency-Key": "creation-api-policy-001",
                    "If-Match": policy.headers["ETag"],
                },
                json={"mode": "guided"},
            )
            assert changed_policy.status_code == 200, changed_policy.text
            assert_contract_response(
                changed_policy,
                operation_id="updateProjectAutomationPolicy",
                status="200",
            )
            project_detail = await client.get(f"/api/v2/projects/{project_id}")
            project_list = await client.get("/api/v2/projects")
            workflow = await client.get(f"/api/v2/projects/{project_id}/workflow")
            assert project_detail.status_code == 200, project_detail.text
            assert project_detail.json()["data"]["execution_mode"] == "guided"
            assert project_detail.headers["ETag"] != initial_project_etag
            assert project_list.status_code == 200, project_list.text
            assert project_list.json()["data"]["items"][0]["execution_mode"] == "guided"
            assert workflow.status_code == 200, workflow.text
            assert workflow.json()["data"]["project"]["execution_mode"] == "guided"
            stale_policy = await client.patch(
                f"/api/v2/projects/{project_id}/automation-policy",
                headers={
                    "Idempotency-Key": "creation-api-policy-stale-001",
                    "If-Match": policy.headers["ETag"],
                },
                json={"mode": "automatic"},
            )
            assert stale_policy.status_code == 409, stale_policy.text
            assert stale_policy.json()["error"]["code"] == "EDIT_CONFLICT"

            factory = build_session_factory(app.state.database_engine)
            with factory() as session, session.begin():
                project = session.get(Project, project_id)
                assert project is not None
                slot_key = "lesson.01.ppt.page.05.main_visual"
                declare_target_slot(session, actor, project, slot_key)
                package, _ = seed_project_package(session, actor, project, slot_key)
                file_version = seed_file_version(session, actor)

            batch = await client.post(
                "/api/v2/creation-batches",
                headers={"Idempotency-Key": "creation-api-batch-001"},
                json={
                    "source_kind": "project",
                    "studio_type": "image",
                    "title": "PPT images",
                    "creation_package_id": str(package.id),
                },
            )
            assert batch.status_code == 201, batch.text
            assert_contract_response(batch, operation_id="createCreationBatch", status="201")
            item_id = UUID(batch.json()["data"]["items"][0]["id"])

            prompt = await client.post(
                f"/api/v2/creation-items/{item_id}/prompt-versions",
                headers={"Idempotency-Key": "creation-api-prompt-001"},
                json={
                    "business_prompt": "Show three percentage examples.",
                    "reference_asset_version_ids": [],
                    "output_spec": {"mime_type": "image/png"},
                    "generation_profile": "quality",
                },
            )
            assert prompt.status_code == 201, prompt.text
            assert_contract_response(
                prompt,
                operation_id="saveCreationPromptVersion",
                status="201",
            )
            prompt_id = UUID(prompt.json()["data"]["id"])

            generated = await client.post(
                f"/api/v2/creation-items/{item_id}/generate",
                headers={"Idempotency-Key": "creation-api-generate-001"},
                json={"prompt_version_id": str(prompt_id), "candidate_count": 1},
            )
            assert generated.status_code == 202, generated.text
            assert_contract_response(
                generated,
                operation_id="generateCreationItem",
                status="202",
            )
            job_id = UUID(generated.json()["data"]["job_id"])

            with factory() as session, session.begin():
                result = GenerationResult(
                    id=new_uuid7(),
                    organization_id=actor.organization_id,
                    creation_item_id=item_id,
                    generation_job_id=job_id,
                    candidate_no=1,
                    status="available",
                    file_asset_version_id=file_version.id,
                    output_json={},
                    created_at=utc_now(),
                )
                session.add(result)

            adopted = await client.post(
                f"/api/v2/generation-results/{result.id}/adoptions",
                headers={"Idempotency-Key": "creation-api-adopt-001"},
                json={"reason": "Best fit"},
            )
            assert adopted.status_code == 201, adopted.text
            assert_contract_response(
                adopted,
                operation_id="adoptGenerationResult",
                status="201",
            )
            adoption_id = UUID(adopted.json()["data"]["id"])
            save_headers = {"Idempotency-Key": "creation-api-save-001"}
            save_payload = {
                "source_kind": "project",
                "replace_mode": "reject_if_occupied",
            }
            saved = await client.post(
                f"/api/v2/adoptions/{adoption_id}/save-to-project",
                headers=save_headers,
                json=save_payload,
            )
            replayed = await client.post(
                f"/api/v2/adoptions/{adoption_id}/save-to-project",
                headers=save_headers,
                json=save_payload,
            )
            assert saved.status_code == replayed.status_code == 200
            assert_contract_response(saved, operation_id="saveAdoptionToProject", status="200")
            assert saved.json()["data"]["operation_id"] == replayed.json()["data"]["operation_id"]
            assert replayed.json()["data"]["idempotent_replay"] is True

            legacy_saved = await client.post(
                f"/api/v2/generation-results/{result.id}/save-to-project",
                headers={"Idempotency-Key": "k" * 128},
                json={
                    "project_id": str(project_id),
                    "slot_key": slot_key,
                    "replace_mode": "replace_active",
                },
            )
            assert legacy_saved.status_code == 200, legacy_saved.text
            assert_contract_response(
                legacy_saved,
                operation_id="saveGenerationResultToProject",
                status="200",
            )
            assert (
                legacy_saved.json()["data"]["operation_id"] != saved.json()["data"]["operation_id"]
            )
    finally:
        app.state.database_engine.dispose()
