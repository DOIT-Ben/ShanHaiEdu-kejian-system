from __future__ import annotations

import hashlib
from pathlib import Path
from secrets import token_urlsafe
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from apps.api.artifact_quality.models import ArtifactQualityReport
from apps.api.artifact_quality.runtime import runtime_quality_validator_registry
from apps.api.assets.material_parser import ParseLimits
from apps.api.assets.pypdf_parser import PypdfMaterialParser
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_session_factory
from apps.api.main import create_app
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from tests.conftest import run_migration
from tests.fakes.identity import TEST_PRINCIPAL_ID
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.identity_session_support import (
    APP_ORIGIN,
    create_project,
    login,
    runtime_settings,
    seed_teacher,
    session_client,
)
from tests.integration.r1_teacher_flow_support import (
    generated_pdf as _generated_pdf,
)
from tests.integration.r1_teacher_flow_support import (
    intro_output as _intro_output,
)
from tests.integration.r1_teacher_flow_support import (
    lesson_plan_output as _lesson_plan_output,
)
from tests.integration.r1_teacher_flow_support import (
    two_lesson_division_output as _two_lesson_division_output,
)
from workers.artifact_quality import execute_artifact_quality_node
from workers.material_parse import MaterialParseJobRunner
from workers.node_execution import execute_node_execution_job

ROOT = Path(__file__).resolve().parents[2]


async def test_r1_teacher_flow_persists_and_recovers(
    postgres_database_url: str,
    tmp_path: Path,
) -> None:
    run_migration(postgres_database_url, "head")
    settings = runtime_settings(
        postgres_database_url,
        access_code=token_urlsafe(32),
        csrf_secret=token_urlsafe(48),
    )
    storage = FakeObjectStorage()
    app = create_app(settings=settings, object_storage=storage)
    restarted = None
    seed_teacher(app)
    factory = build_session_factory(app.state.database_engine)
    with factory() as session, session.begin():
        ContentReleasePublisher(session).publish(
            load_builtin_courseware_release(ROOT),
            published_by=TEST_PRINCIPAL_ID,
        )

    try:
        client, _ = session_client(app)
        async with client:
            authenticated = await login(client, settings.session_access_code.get_secret_value())
            assert authenticated.status_code == 201, authenticated.text
            session_snapshot = authenticated.json()["data"]
            csrf_token = session_snapshot["csrf_token"]

            created = await create_project(
                client,
                csrf_token=csrf_token,
                idempotency_key="r1-flow-project-001",
                title="认识1到5真实纵向链",
            )
            assert created.status_code == 201, created.text
            project_id = UUID(created.json()["data"]["id"])

            pdf = _generated_pdf()
            checksum = hashlib.sha256(pdf).hexdigest()
            upload = await client.post(
                f"/api/v2/projects/{project_id}/materials/uploads",
                headers=_write_headers(csrf_token, "r1-flow-upload-001"),
                json={
                    "filename": "numbers-one-to-five.pdf",
                    "media_type": "application/pdf",
                    "size_bytes": len(pdf),
                    "sha256": checksum,
                },
            )
            assert upload.status_code == 201, upload.text
            upload_data = upload.json()["data"]
            assert storage.last_presigned is not None
            uploaded = storage.put_bytes(
                bucket=storage.last_presigned.bucket,
                key=storage.last_presigned.key,
                payload=pdf,
                media_type="application/pdf",
            )
            confirmed = await client.post(
                f"/api/v2/projects/{project_id}/materials/{upload_data['material_id']}/confirm",
                headers=_write_headers(csrf_token, "r1-flow-confirm-001"),
                json={
                    "upload_session_id": upload_data["upload_session_id"],
                    "etag": uploaded.etag,
                    "size_bytes": len(pdf),
                    "sha256": checksum,
                },
            )
            assert confirmed.status_code == 202, confirmed.text
            parse_job_id = UUID(confirmed.json()["data"]["job_id"])
            parse_outcome = MaterialParseJobRunner(
                factory,
                storage=storage,
                parser=PypdfMaterialParser(),
                limits=ParseLimits(),
                temp_root=tmp_path,
                settings=settings,
            ).run(parse_job_id, worker_id="r1-flow-material-parser")
            assert parse_outcome == "succeeded"

            parses = await client.get(
                f"/api/v2/projects/{project_id}/materials/{upload_data['material_id']}"
                "/parse-versions"
            )
            assert parses.status_code == 200, parses.text
            parse_data = parses.json()["data"]["items"]
            assert len(parse_data) == 1
            assert parse_data[0]["status"] == "succeeded"
            assert parse_data[0]["parser_name"] == "pypdf"
            parse_version_id = UUID(parse_data[0]["id"])

            scope = await client.post(
                f"/api/v2/projects/{project_id}/material-scope/versions",
                headers=_write_headers(csrf_token, "r1-flow-scope-001"),
                json={
                    "source_material_id": upload_data["material_id"],
                    "material_parse_version_id": str(parse_version_id),
                    "page_start": 1,
                    "page_end": 2,
                },
            )
            assert scope.status_code == 201, scope.text
            scope_version = scope.json()["data"]["current_submitted_version"]
            scope_version_id = UUID(scope_version["id"])
            scope_content = scope_version["content"]
            evidence_keys = scope_content["approved_evidence_keys"]
            assert len(evidence_keys) >= 2
            await _approve_version(
                client,
                csrf_token=csrf_token,
                version_id=scope_version_id,
                suffix="scope",
            )

            division_output = _two_lesson_division_output(evidence_keys)
            prepared_division = await client.post(
                f"/api/v2/projects/{project_id}/lesson-division/node-runs",
                headers=_write_headers(csrf_token, "r1-flow-division-prepare"),
                json={"material_scope_artifact_version_id": str(scope_version_id)},
            )
            assert prepared_division.status_code == 200, prepared_division.text
            division_version_id = await _run_node(
                client,
                settings=settings,
                factory=factory,
                csrf_token=csrf_token,
                node_run_id=UUID(prepared_division.json()["data"]["id"]),
                output=division_output,
                suffix="division",
            )
            await _validate_and_approve(
                client,
                database_url=postgres_database_url,
                factory=factory,
                csrf_token=csrf_token,
                version_id=division_version_id,
                suffix="division",
            )

            assert {
                "requested_lesson_count": scope_content.get("requested_lesson_count"),
                "lesson_type_preferences": scope_content.get("lesson_type_preferences"),
                "special_requirements": scope_content.get("special_requirements"),
            } == {
                "requested_lesson_count": None,
                "lesson_type_preferences": [],
                "special_requirements": "",
            }

            lessons_response = await client.get(f"/api/v2/projects/{project_id}/lessons")
            assert lessons_response.status_code == 200, lessons_response.text
            lessons = lessons_response.json()["data"]["items"]
            assert [lesson["lesson_key"] for lesson in lessons] == ["LESSON-001", "LESSON-002"]

            approved_plan_versions: dict[UUID, UUID] = {}
            units_by_key = {
                unit["lesson_unit_key"]: unit for unit in division_output["lesson_units"]
            }
            for index, lesson in enumerate(lessons, start=1):
                lesson_id = UUID(lesson["id"])
                unit = units_by_key[lesson["lesson_key"]]
                prepared_plan = await client.post(
                    f"/api/v2/lessons/{lesson_id}/lesson-plan/node-runs",
                    headers=_write_headers(csrf_token, f"r1-flow-plan-{index}-prepare"),
                )
                assert prepared_plan.status_code == 200, prepared_plan.text
                plan_version_id = await _run_node(
                    client,
                    settings=settings,
                    factory=factory,
                    csrf_token=csrf_token,
                    node_run_id=UUID(prepared_plan.json()["data"]["id"]),
                    output=_lesson_plan_output(unit, index),
                    suffix=f"plan-{index}",
                )
                await _validate_and_approve(
                    client,
                    database_url=postgres_database_url,
                    factory=factory,
                    csrf_token=csrf_token,
                    version_id=plan_version_id,
                    suffix=f"plan-{index}",
                )
                approved_plan_versions[lesson_id] = plan_version_id

            first_lesson_id = UUID(lessons[0]["id"])
            first_unit = units_by_key[lessons[0]["lesson_key"]]
            intro_output = _intro_output(first_unit)
            prepared_intro = await client.post(
                f"/api/v2/lessons/{first_lesson_id}/intro-options/node-runs",
                headers=_write_headers(csrf_token, "r1-flow-intro-prepare"),
                json={"generation_mode": "default_nine"},
            )
            assert prepared_intro.status_code == 200, prepared_intro.text
            intro_version_id = await _run_node(
                client,
                settings=settings,
                factory=factory,
                csrf_token=csrf_token,
                node_run_id=UUID(prepared_intro.json()["data"]["id"]),
                output=intro_output,
                suffix="intro",
            )
            await _validate_and_approve(
                client,
                database_url=postgres_database_url,
                factory=factory,
                csrf_token=csrf_token,
                version_id=intro_version_id,
                suffix="intro",
            )

            selected_option_key = intro_output["recommendation_summary"]["recommended_option_key"]
            selected = await client.post(
                f"/api/v2/lessons/{first_lesson_id}/intro-selections",
                headers=_write_headers(csrf_token, "r1-flow-intro-select"),
                json={
                    "artifact_version_id": str(intro_version_id),
                    "option_key": selected_option_key,
                },
            )
            assert selected.status_code == 201, selected.text
            assert selected.json()["data"]["active"] is True
            session_cookie = client.cookies.get("shanhai_session")
            assert session_cookie

        app.state.database_engine.dispose()
        restarted = create_app(settings=settings, object_storage=storage)
        recovered_client, _ = session_client(restarted)
        recovered_client.cookies.set(
            "shanhai_session",
            session_cookie,
            domain="teacher.shanhai.test",
        )
        async with recovered_client:
            recovered_session = await recovered_client.get("/api/v2/auth/session")
            assert recovered_session.status_code == 200, recovered_session.text
            assert recovered_session.json()["data"] == session_snapshot

            recovered_project = await recovered_client.get(f"/api/v2/projects/{project_id}")
            recovered_materials = await recovered_client.get(
                f"/api/v2/projects/{project_id}/materials"
            )
            recovered_lessons = await recovered_client.get(f"/api/v2/projects/{project_id}/lessons")
            recovered_artifacts = await recovered_client.get(
                f"/api/v2/projects/{project_id}/artifacts",
                params={"page[limit]": 100},
            )
            recovered_intro = await recovered_client.get(
                f"/api/v2/lessons/{first_lesson_id}/intro-options"
            )

        assert recovered_project.status_code == 200, recovered_project.text
        assert recovered_materials.status_code == 200, recovered_materials.text
        assert len(recovered_materials.json()["data"]["items"]) == 1
        recovered_lesson_items = recovered_lessons.json()["data"]["items"]
        assert [item["lesson_key"] for item in recovered_lesson_items] == [
            "LESSON-001",
            "LESSON-002",
        ]
        artifact_items = recovered_artifacts.json()["data"]["items"]
        approved_plans = [
            item
            for item in artifact_items
            if item["artifact_type"] == "lesson_plan" and item["status"] == "approved"
        ]
        assert {UUID(item["lesson_unit_id"]) for item in approved_plans} == set(
            approved_plan_versions
        )
        assert {UUID(item["current_approved_version"]["id"]) for item in approved_plans} == set(
            approved_plan_versions.values()
        )
        intro_data = recovered_intro.json()["data"]
        assert intro_data["current_approved_version_id"] == str(intro_version_id)
        expected_options = sorted(
            intro_output["options"],
            key=lambda option: (-int(option["recommendation_score"]), option["option_key"]),
        )
        assert intro_data["display_version"]["option_set"]["options"] == expected_options
        assert intro_data["current_selection"]["option_key"] == selected_option_key
        assert intro_data["current_selection"]["active"] is True
    finally:
        if restarted is not None:
            restarted.state.database_engine.dispose()
        else:
            app.state.database_engine.dispose()


def _write_headers(csrf_token: str, idempotency_key: str) -> dict[str, str]:
    return {
        "Origin": APP_ORIGIN,
        "X-CSRF-Token": csrf_token,
        "Idempotency-Key": idempotency_key,
    }


async def _run_node(
    client: httpx.AsyncClient,
    *,
    settings,
    factory,
    csrf_token: str,
    node_run_id: UUID,
    output: dict[str, Any],
    suffix: str,
) -> UUID:
    started = await client.post(
        f"/api/v2/node-runs/{node_run_id}/start",
        headers=_write_headers(csrf_token, f"r1-flow-{suffix}-start"),
    )
    assert started.status_code == 202, started.text
    job_id = UUID(started.json()["data"]["job_id"])
    provider = DeterministicNodeOutputProvider(output)
    gateway = ModelGateway(
        {
            ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider,
            ModelCapability.TEXT_STRUCTURED_CREATIVE_EDUCATION: provider,
        },
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    outcome = await execute_node_execution_job(
        job_id,
        worker_id=f"r1-flow-{suffix}-worker",
        model=gateway,
        settings=settings,
    )
    job = await client.get(f"/api/v2/generation-jobs/{job_id}")
    assert job.status_code == 200, job.text
    job_data = job.json()["data"]
    with factory() as session:
        attempts = session.scalars(
            select(GenerationAttempt)
            .where(GenerationAttempt.generation_job_id == job_id)
            .order_by(GenerationAttempt.attempt_no)
        ).all()
    assert outcome == "succeeded", {
        "job_error_code": job_data["error_code"],
        "provider_calls": provider.calls,
        "attempt_states": [
            {"status": attempt.status, "error_code": attempt.error_code} for attempt in attempts
        ],
    }
    assert provider.calls == 1
    assert job_data["status"] == "succeeded"
    assert job_data["node_run_id"] == str(node_run_id)
    assert job_data["result_artifact_version_id"] is not None
    return UUID(job_data["result_artifact_version_id"])


async def _validate_and_approve(
    client: httpx.AsyncClient,
    *,
    database_url: str,
    factory,
    csrf_token: str,
    version_id: UUID,
    suffix: str,
) -> None:
    queued = await client.post(
        f"/api/v2/artifact-versions/{version_id}/quality-validations",
        headers=_write_headers(csrf_token, f"r1-flow-{suffix}-quality"),
    )
    assert queued.status_code == 202, queued.text
    validate_node_id = UUID(queued.json()["data"]["node_run_id"])
    report = execute_artifact_quality_node(
        database_url,
        validate_node_id,
        runtime_quality_validator_registry(),
    )
    assert report is not None
    with factory() as session:
        persisted_report = session.get(ArtifactQualityReport, report.report_id)
        assert persisted_report is not None
        findings = persisted_report.findings_json
    assert report.conclusion == "passed", findings
    await _approve_version(
        client,
        csrf_token=csrf_token,
        version_id=version_id,
        suffix=suffix,
    )


async def _approve_version(
    client: httpx.AsyncClient,
    *,
    csrf_token: str,
    version_id: UUID,
    suffix: str,
) -> None:
    approved = await client.post(
        f"/api/v2/artifact-versions/{version_id}/approvals",
        headers=_write_headers(csrf_token, f"r1-flow-{suffix}-approve"),
        json={"action": "approve", "comment": f"Approve exact R1 {suffix} facts."},
    )
    assert approved.status_code == 201, approved.text
    assert approved.json()["data"]["artifact_version_id"] == str(version_id)
