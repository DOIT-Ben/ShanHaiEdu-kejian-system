from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.ids import new_uuid7
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import (
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    TextModelRequest,
)
from apps.api.model_gateway.fake import DeterministicFakeTextProvider, FakeScenario
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.identity import seed_test_actor
from workflow.node_state import NodeStatus


def test_attempt_numbers_are_unique_and_usage_is_append_only(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
            run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
            node = WorkflowRuntimeService(session, actor).create_project_node_run(
                run.id,
                node_key="prepare",
                status=NodeStatus.READY,
            )
            attempt = GenerationAttempt(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                project_id=project.id,
                node_run_id=node.id,
                generation_job_id=None,
                attempt_no=1,
                request_id="req-audit-1",
                capability="text.smoke",
                provider_name="deterministic-fake",
                provider_model="fake-text-v1",
                route_reason="configured_primary",
                status="succeeded",
                request_hash="a" * 64,
                provider_request_id="fake:req-audit-1",
                submitted_at=utc_now(),
                finished_at=utc_now(),
                error_code=None,
                error_details_json={},
                latency_ms=7,
            )
            usage = UsageRecord(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                user_id=actor.user_id,
                project_id=project.id,
                node_run_id=node.id,
                generation_attempt_id=attempt.id,
                capability="text.smoke",
                provider_name="deterministic-fake",
                provider_model="fake-text-v1",
                input_units_json={"prompt_tokens": 8},
                output_units_json={"completion_tokens": 4, "total_tokens": 12},
                actual_cost=Decimal("0.000000"),
                currency="USD",
                latency_ms=7,
            )
            session.add_all((attempt, usage))

        assert usage.actual_cost == Decimal("0.000000")

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                GenerationAttempt(
                    id=new_uuid7(),
                    organization_id=actor.organization_id,
                    project_id=project.id,
                    node_run_id=node.id,
                    generation_job_id=None,
                    attempt_no=1,
                    request_id="req-audit-duplicate",
                    capability="text.smoke",
                    provider_name="deterministic-fake",
                    provider_model="fake-text-v1",
                    route_reason="configured_primary",
                    status="running",
                    request_hash="b" * 64,
                    provider_request_id=None,
                    submitted_at=utc_now(),
                    finished_at=None,
                    error_code=None,
                    error_details_json={},
                    latency_ms=None,
                )
            )
            session.flush()

        with pytest.raises(DBAPIError), session.begin_nested():
            persisted = session.get(UsageRecord, usage.id)
            assert persisted is not None
            persisted.actual_cost = Decimal("9.000000")
            session.flush()


def test_attempt_requires_consistent_terminal_fields(migrated_database_url: str) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
        node = WorkflowRuntimeService(session, actor).create_project_node_run(
            run.id,
            node_key="prepare",
            status=NodeStatus.READY,
        )
        session.add(
            GenerationAttempt(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                project_id=project.id,
                node_run_id=node.id,
                generation_job_id=None,
                attempt_no=1,
                request_id="req-invalid-terminal",
                capability="text.smoke",
                provider_name="deterministic-fake",
                provider_model="fake-text-v1",
                route_reason="configured_primary",
                status="failed",
                request_hash="c" * 64,
                provider_request_id=None,
                submitted_at=utc_now(),
                finished_at=None,
                error_code=None,
                error_details_json={},
                latency_ms=None,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


async def test_fake_gateway_success_and_failure_share_persistent_safe_audit(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
        node = WorkflowRuntimeService(session, actor).create_project_node_run(
            run.id,
            node_key="prepare",
            status=NodeStatus.READY,
        )

    audit_context = ModelAuditContext(
        organization_id=actor.organization_id,
        user_id=actor.user_id,
        project_id=project.id,
        node_run_id=node.id,
        generation_job_id=None,
    )
    private_prompt = "PRIVATE_PROMPT_MARKER"
    success = ModelGateway(
        {ModelCapability.TEXT_SMOKE: DeterministicFakeTextProvider()},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    result = await success.generate_text(
        TextModelRequest(
            capability=ModelCapability.TEXT_SMOKE,
            request_id="req-persistent-success",
            prompt=private_prompt,
        ),
        audit_context=audit_context,
    )
    failed = ModelGateway(
        {ModelCapability.TEXT_SMOKE: DeterministicFakeTextProvider(FakeScenario.RATE_LIMITED)},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    with pytest.raises(ModelGatewayError):
        await failed.generate_text(
            TextModelRequest(
                capability=ModelCapability.TEXT_SMOKE,
                request_id="req-persistent-failure",
                prompt=private_prompt,
            ),
            audit_context=audit_context,
        )

    with factory() as session:
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.node_run_id == node.id)
                .order_by(GenerationAttempt.attempt_no)
            )
        )
        usage = list(
            session.scalars(
                select(UsageRecord)
                .where(UsageRecord.node_run_id == node.id)
                .order_by(UsageRecord.created_at)
            )
        )

    assert [attempt.status for attempt in attempts] == ["succeeded", "failed"]
    assert [attempt.attempt_no for attempt in attempts] == [1, 2]
    assert attempts[1].error_code == "PROVIDER_RATE_LIMITED"
    assert len(usage) == 2
    assert usage[0].actual_cost == Decimal("0.000000")
    assert usage[0].input_units_json == {"prompt_tokens": 8}
    assert usage[1].input_units_json == {"prompt_tokens": 0}
    persisted = json.dumps(
        {
            "attempts": [
                {
                    "request_hash": attempt.request_hash,
                    "error": attempt.error_details_json,
                }
                for attempt in attempts
            ],
            "usage": [record.output_units_json for record in usage],
        }
    )
    assert private_prompt not in persisted
    assert result.text not in persisted
