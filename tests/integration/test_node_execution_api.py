from __future__ import annotations

import json

import httpx
from sqlalchemy import select

from apps.api.artifacts.models import ArtifactVersion
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory
from apps.api.lessons.runtime_service import LessonDivisionRuntimeService
from apps.api.main import create_app
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import ModelCapability
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.settings import Settings
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.identity import override_test_identity, seed_test_actor
from tests.integration.test_lesson_division_runtime import (
    GOLDEN_CASE,
    ROOT,
    _seed_material_and_scope,
)


async def test_generated_lesson_division_can_be_validated_and_approved_over_http(
    migrated_database_url: str,
    monkeypatch,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    case = json.loads(GOLDEN_CASE.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]

    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        published = ContentReleasePublisher(session).publish(
            load_builtin_courseware_release(ROOT),
            published_by=actor.principal_id,
        )
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="HTTP lesson division", knowledge_point="1-5")
        )
        definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.content_package_version_id
                == published.content_package_version_id,
                ContentDefinitionVersion.definition_key == "lesson.division.generate.output",
            )
        )
        assert definition is not None
        _seed_material_and_scope(
            session,
            actor,
            project.id,
            definition.id,
            case,
            approved_evidence_keys=None,
        )
        node_run_id = LessonDivisionRuntimeService(session, actor).initialize(
            project.id
        ).generate_node_run_id

    provider = DeterministicNodeOutputProvider(output)
    gateway = ModelGateway(
        {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    monkeypatch.setattr(
        "apps.api.node_execution.router.build_real_text_gateway",
        lambda *_args, **_kwargs: (gateway, provider),
    )
    app = create_app(
        settings=Settings(_env_file=None, environment="test"),
        session_factory=factory,
    )
    override_test_identity(app, actor)

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v2/node-runs/{node_run_id}/start",
                headers={"Idempotency-Key": "issue-11-start-node-001"},
                json={},
            )

            assert response.status_code == 200, response.text
            result = response.json()["data"]
            approved = await client.post(
                f"/api/v2/artifact-versions/{result['artifact_version_id']}/quality-approvals",
                headers={"Idempotency-Key": "issue-11-approve-001"},
                json={"comment": "Ready for lesson planning"},
            )

        assert approved.status_code == 201, approved.text
        assert_contract_response(response, operation_id="startNodeRun", status="200")
        assert_contract_response(
            approved,
            operation_id="validateAndApproveArtifactVersion",
            status="201",
        )
        assert result["node_run_id"] == str(node_run_id)
        assert approved.json()["data"]["artifact_version_id"] == result["artifact_version_id"]
        assert approved.json()["data"]["action"] == "approve"
        assert provider.calls == 1
        with factory() as session:
            version = session.get(ArtifactVersion, result["artifact_version_id"])
            assert version is not None
            assert version.artifact.status == "approved"
            assert session.get(GenerationAttempt, result["attempt_id"]) is not None
            assert session.get(UsageRecord, result["usage_id"]) is not None
    finally:
        engine.dispose()
