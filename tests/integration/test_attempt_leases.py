from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import select

from apps.api.database import build_engine, build_session_factory
from apps.api.model_gateway.audit import AttemptRequestAudit, SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt
from apps.api.model_gateway.contracts import ModelAuditContext
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.identity import seed_test_actor
from workflow.node_state import NodeStatus


def _seed_context(factory) -> ModelAuditContext:
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Attempt leases", knowledge_point="One half")
        )
        run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
        node = WorkflowRuntimeService(session, actor).create_project_node_run(
            run.id,
            node_key="prepare",
            status=NodeStatus.READY,
        )
    return ModelAuditContext(
        organization_id=actor.organization_id,
        user_id=actor.user_id,
        project_id=project.id,
        node_run_id=node.id,
        generation_job_id=None,
    )


def _request(request_id: str) -> AttemptRequestAudit:
    return AttemptRequestAudit(
        request_id=request_id,
        capability="text.smoke",
        request_hash=request_id.encode().hex().ljust(64, "0")[:64],
        operation_kind="text_generate",
    )


def test_start_persists_an_owned_attempt_lease(migrated_database_url: str) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)

    handle = SqlAlchemyAttemptAuditSink(factory, lease_seconds=30).start(
        context,
        _request("req-attempt-lease"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )

    with factory() as session:
        attempt = session.get(GenerationAttempt, handle.attempt_id)

    assert attempt is not None
    assert attempt.attempt_no == 1
    assert attempt.operation_kind == "text_generate"
    assert attempt.lease_owner == handle.lease_owner
    assert attempt.heartbeat_at is not None
    assert attempt.lease_expires_at is not None
    assert attempt.lease_expires_at > attempt.heartbeat_at


def test_concurrent_workers_allocate_distinct_attempt_numbers(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    barrier = Barrier(2)

    def start(index: int):
        barrier.wait()
        return SqlAlchemyAttemptAuditSink(factory).start(
            context,
            _request(f"req-concurrent-attempt-{index}"),
            provider_name="provider-test",
            provider_model="model-test",
            route_reason="configured_primary",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        handles = list(executor.map(start, (1, 2)))

    with factory() as session:
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.node_run_id == context.node_run_id)
                .order_by(GenerationAttempt.attempt_no)
            )
        )

    assert len({handle.attempt_id for handle in handles}) == 2
    assert [attempt.attempt_no for attempt in attempts] == [1, 2]
