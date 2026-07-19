from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.ids import new_uuid7
from apps.api.model_gateway.attempt_recovery import AttemptRecoveryCoordinator
from apps.api.model_gateway.audit import (
    AttemptHeartbeat,
    AttemptRequestAudit,
    DuplicateAttemptDelivery,
    SqlAlchemyAttemptAuditSink,
)
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import GatewayErrorCode, ModelAuditContext, ModelGatewayError
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


def _request(request_id: str, *, operation_kind: str = "text_generate") -> AttemptRequestAudit:
    return AttemptRequestAudit(
        request_id=request_id,
        capability="text.smoke",
        request_hash=request_id.encode().hex().ljust(64, "0")[:64],
        operation_kind=operation_kind,
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


def test_duplicate_delivery_does_not_create_another_attempt(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    sink = SqlAlchemyAttemptAuditSink(factory)
    sink.start(
        context,
        _request("req-duplicate-delivery"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )

    with pytest.raises(DuplicateAttemptDelivery):
        sink.start(
            context,
            _request("req-duplicate-delivery"),
            provider_name="provider-test",
            provider_model="model-test",
            route_reason="configured_primary",
        )

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(GenerationAttempt)) == 1


def test_persisted_cancel_is_observed_by_heartbeat_and_terminal_audit(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    sink = SqlAlchemyAttemptAuditSink(factory)
    lease = sink.start(
        context,
        _request("req-cancel-attempt"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )

    assert AttemptRecoveryCoordinator(factory).request_cancel(lease.attempt_id) is True
    assert sink.heartbeat(lease, context) == AttemptHeartbeat.CANCEL_REQUESTED
    sink.fail(
        lease,
        context,
        ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False),
        latency_ms=9,
    )

    with factory() as session:
        attempt = session.get(GenerationAttempt, lease.attempt_id)
        usage_count = session.scalar(
            select(func.count())
            .select_from(UsageRecord)
            .where(UsageRecord.generation_attempt_id == lease.attempt_id)
        )

    assert attempt is not None and attempt.status == "cancelled"
    assert attempt.lease_owner is None and attempt.lease_expires_at is None
    assert usage_count == 1


def test_usage_record_cannot_bind_to_a_running_attempt(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    lease = SqlAlchemyAttemptAuditSink(factory).start(
        context,
        _request("req-running-usage"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )

    with pytest.raises(IntegrityError), factory() as session, session.begin():
        session.add(_usage_record(lease.attempt_id, context))
        session.flush()


def test_two_recovery_workers_terminalize_expired_attempts_once(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    sink = SqlAlchemyAttemptAuditSink(factory)
    text_lease = sink.start(
        context,
        _request("req-expired-text"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )
    video_lease = sink.start(
        context,
        _request("req-expired-video", operation_kind="video_submit"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )
    with factory() as session, session.begin():
        attempts = list(
            session.scalars(
                select(GenerationAttempt).where(
                    GenerationAttempt.id.in_((text_lease.attempt_id, video_lease.attempt_id))
                )
            )
        )
        expired_at = utc_now()
        for attempt in attempts:
            attempt.heartbeat_at = expired_at - timedelta(seconds=2)
            attempt.lease_expires_at = expired_at - timedelta(seconds=1)

    assert sink.heartbeat(text_lease, context) == AttemptHeartbeat.LOST
    with pytest.raises(RuntimeError):
        sink.fail(
            text_lease,
            context,
            ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False),
            latency_ms=9,
        )

    barrier = Barrier(2)

    def recover(_index: int):
        barrier.wait()
        return AttemptRecoveryCoordinator(factory).reconcile()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(recover, (1, 2)))

    assert sum(result.recovered for result in results) == 2
    assert AttemptRecoveryCoordinator(factory).reconcile().recovered == 0
    assert sink.heartbeat(text_lease, context) == AttemptHeartbeat.LOST
    with factory() as session:
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.node_run_id == context.node_run_id)
                .order_by(GenerationAttempt.attempt_no)
            )
        )
        usage = list(
            session.scalars(
                select(UsageRecord)
                .where(UsageRecord.node_run_id == context.node_run_id)
                .order_by(UsageRecord.created_at)
            )
        )

    assert [attempt.status for attempt in attempts] == ["failed", "submission_unknown"]
    assert attempts[0].error_code == "MODEL_ATTEMPT_LEASE_EXPIRED"
    assert attempts[1].error_code == "MODEL_SUBMISSION_UNKNOWN"
    assert len(usage) == 2
    assert all(record.actual_cost is None for record in usage)


def test_recovery_reuses_a_legacy_usage_record_instead_of_inserting_again(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    sink = SqlAlchemyAttemptAuditSink(factory)
    lease = sink.start(
        context,
        _request("req-expired-with-usage"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )
    with factory() as session, session.begin():
        attempt = session.get(GenerationAttempt, lease.attempt_id, with_for_update=True)
        assert attempt is not None
        expired_at = utc_now()
        attempt.heartbeat_at = expired_at - timedelta(seconds=2)
        attempt.lease_expires_at = expired_at - timedelta(seconds=1)
        session.execute(
            text("ALTER TABLE usage_records DISABLE TRIGGER trg_usage_record_terminal_attempt")
        )
        session.add(_usage_record(lease.attempt_id, context))
        session.flush()
        session.execute(
            text("ALTER TABLE usage_records ENABLE TRIGGER trg_usage_record_terminal_attempt")
        )

    result = AttemptRecoveryCoordinator(factory).reconcile()

    with factory() as session:
        attempt = session.get(GenerationAttempt, lease.attempt_id)
        usage_count = session.scalar(
            select(func.count())
            .select_from(UsageRecord)
            .where(UsageRecord.generation_attempt_id == lease.attempt_id)
        )
    assert result.failed == 1
    assert attempt is not None and attempt.status == "failed"
    assert usage_count == 1


def _usage_record(attempt_id: UUID, context: ModelAuditContext) -> UsageRecord:
    return UsageRecord(
        id=new_uuid7(),
        organization_id=context.organization_id,
        user_id=context.user_id,
        project_id=context.project_id,
        node_run_id=context.node_run_id,
        generation_attempt_id=attempt_id,
        capability="text.smoke",
        provider_name="provider-test",
        provider_model="model-test",
        input_units_json={"prompt_tokens": 0},
        output_units_json={"completion_tokens": 0, "total_tokens": 0},
        pricing_version=None,
        estimated_cost=None,
        actual_cost=None,
        currency="USD",
        latency_ms=0,
    )
