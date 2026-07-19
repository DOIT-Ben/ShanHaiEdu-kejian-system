from __future__ import annotations

from collections.abc import Collection
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Event
from uuid import UUID

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.context import ActorContext
from apps.api.identity.models import Organization
from apps.api.ids import new_uuid7
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobBinding, GenerationJobCancellationReader
from apps.api.model_gateway.attempt_recovery import AttemptRecoveryCoordinator
from apps.api.model_gateway.audit import (
    AttemptHeartbeat,
    AttemptRequestAudit,
    AttemptSuccessAudit,
    DuplicateAttemptDelivery,
    SqlAlchemyAttemptAuditSink,
)
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ModelAuditContext,
    ModelGatewayError,
    ModelUsage,
)
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.identity import TEST_PRINCIPAL_ID, seed_test_actor
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


def _actor_for(context: ModelAuditContext) -> ActorContext:
    return ActorContext(
        organization_id=context.organization_id,
        principal_id=TEST_PRINCIPAL_ID,
        user_id=context.user_id,
        actor_type="user",
        organization_role="member",
    )


def _add_job(
    session,
    context: ModelAuditContext,
    *,
    organization_id: UUID | None = None,
    project_id: UUID | None = None,
    job_type: str = "creation.item",
    status: str = "running",
) -> GenerationJob:
    job = GenerationJob(
        id=new_uuid7(),
        organization_id=organization_id or context.organization_id,
        project_id=project_id or context.project_id,
        job_type=job_type,
        status=status,
        progress_percent=0,
        priority=100,
        cancel_requested_at=utc_now() if status == "cancel_requested" else None,
        created_by=TEST_PRINCIPAL_ID,
        updated_by=TEST_PRINCIPAL_ID,
    )
    session.add(job)
    session.flush()
    return job


def _add_running_attempt(
    session,
    context: ModelAuditContext,
    *,
    attempt_no: int,
    request_id: str,
    generation_job_id: UUID | None = None,
    submitted_ago: timedelta = timedelta(minutes=1),
    lease_expired: bool = False,
) -> GenerationAttempt:
    now = utc_now()
    heartbeat_at = now - timedelta(seconds=2) if lease_expired else now
    lease_expires_at = now - timedelta(seconds=1) if lease_expired else now + timedelta(minutes=5)
    attempt = GenerationAttempt(
        id=new_uuid7(),
        organization_id=context.organization_id,
        project_id=context.project_id,
        node_run_id=context.node_run_id,
        generation_job_id=generation_job_id,
        attempt_no=attempt_no,
        request_id=request_id,
        capability="text.smoke",
        operation_kind="text_generate",
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
        status="running",
        request_hash=request_id.encode().hex().ljust(64, "0")[:64],
        provider_request_id=None,
        provider_task_id=None,
        lease_owner=f"owner:{request_id}",
        heartbeat_at=heartbeat_at,
        lease_expires_at=lease_expires_at,
        cancel_requested_at=None,
        submitted_at=now - submitted_ago,
        finished_at=None,
        error_code=None,
        error_details_json={},
        latency_ms=None,
    )
    session.add(attempt)
    session.flush()
    return attempt


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


def test_heartbeat_waiting_on_a_row_lock_cannot_renew_an_expired_lease(
    migrated_database_url: str,
) -> None:
    locking_engine = build_engine(migrated_database_url)
    worker_engine = build_engine(migrated_database_url)
    locking_factory = build_session_factory(locking_engine)
    worker_factory = build_session_factory(worker_engine)
    context = _seed_context(locking_factory)
    sink = SqlAlchemyAttemptAuditSink(worker_factory, lease_seconds=30)
    lease = sink.start(
        context,
        _request("req-heartbeat-lock-expiry"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )
    query_started = Event()

    @event.listens_for(worker_engine, "before_cursor_execute")
    def signal_locking_query(_conn, _cursor, statement, _parameters, _context, _many):
        if "FROM generation_attempts" in statement and "FOR UPDATE" in statement:
            query_started.set()

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with locking_factory() as session, session.begin():
                attempt = session.get(GenerationAttempt, lease.attempt_id, with_for_update=True)
                assert attempt is not None
                database_now = session.scalar(select(func.clock_timestamp()))
                assert database_now is not None
                attempt.lease_expires_at = database_now + timedelta(milliseconds=250)
                session.flush()
                future = executor.submit(sink.heartbeat, lease, context)
                assert query_started.wait(timeout=5)
                session.execute(text("SELECT pg_sleep(0.5)"))

            assert future.result(timeout=5) == AttemptHeartbeat.LOST
    finally:
        event.remove(worker_engine, "before_cursor_execute", signal_locking_query)
        locking_engine.dispose()
        worker_engine.dispose()


def test_terminal_write_waiting_on_a_row_lock_cannot_use_an_expired_lease(
    migrated_database_url: str,
) -> None:
    locking_engine = build_engine(migrated_database_url)
    worker_engine = build_engine(migrated_database_url)
    locking_factory = build_session_factory(locking_engine)
    worker_factory = build_session_factory(worker_engine)
    context = _seed_context(locking_factory)
    sink = SqlAlchemyAttemptAuditSink(worker_factory, lease_seconds=30)
    lease = sink.start(
        context,
        _request("req-terminal-lock-expiry"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )
    query_started = Event()

    @event.listens_for(worker_engine, "before_cursor_execute")
    def signal_locking_query(_conn, _cursor, statement, _parameters, _context, _many):
        if "FROM generation_attempts" in statement and "FOR UPDATE" in statement:
            query_started.set()

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            with locking_factory() as session, session.begin():
                attempt = session.get(GenerationAttempt, lease.attempt_id, with_for_update=True)
                assert attempt is not None
                database_now = session.scalar(select(func.clock_timestamp()))
                assert database_now is not None
                attempt.lease_expires_at = database_now + timedelta(milliseconds=250)
                session.flush()
                future = executor.submit(
                    sink.fail,
                    lease,
                    context,
                    ModelGatewayError(GatewayErrorCode.CANCELLED, retryable=False),
                    latency_ms=9,
                )
                assert query_started.wait(timeout=5)
                session.execute(text("SELECT pg_sleep(0.5)"))

            with pytest.raises(RuntimeError):
                future.result(timeout=5)

        with locking_factory() as session:
            attempt = session.get(GenerationAttempt, lease.attempt_id)
            usage_count = session.scalar(
                select(func.count())
                .select_from(UsageRecord)
                .where(UsageRecord.generation_attempt_id == lease.attempt_id)
            )
        assert attempt is not None and attempt.status == "running"
        assert usage_count == 0
    finally:
        event.remove(worker_engine, "before_cursor_execute", signal_locking_query)
        locking_engine.dispose()
        worker_engine.dispose()


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


def test_generation_job_cancellation_is_synchronized_through_application_reader(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    with factory() as session, session.begin():
        job = GenerationJob(
            id=new_uuid7(),
            organization_id=context.organization_id,
            project_id=context.project_id,
            job_type="creation.item",
            status="running",
            progress_percent=0,
            priority=100,
            created_by=TEST_PRINCIPAL_ID,
            updated_by=TEST_PRINCIPAL_ID,
        )
        session.add(job)
    context = replace(context, generation_job_id=job.id)
    sink = SqlAlchemyAttemptAuditSink(factory)
    lease = sink.start(
        context,
        _request("req-job-cancel-attempt"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )
    with factory() as session, session.begin():
        persisted_job = session.get(GenerationJob, job.id, with_for_update=True)
        assert persisted_job is not None
        persisted_job.status = "cancel_requested"
        persisted_job.cancel_requested_at = utc_now()

    result = AttemptRecoveryCoordinator(factory).reconcile()

    assert result.cancellation_requests == 1
    assert sink.heartbeat(lease, context) == AttemptHeartbeat.CANCEL_REQUESTED


def test_attempt_start_rejects_cross_resource_and_disallowed_jobs(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    other_organization_id = new_uuid7()
    with factory() as session, session.begin():
        other_project = ProjectRepository(session, _actor_for(context)).create(
            CreateProjectRequest(title="Other project", knowledge_point="One third")
        )
        session.add(
            Organization(
                id=other_organization_id,
                slug=f"other-{other_organization_id.hex[:12]}",
                name="Other organization",
                status="active",
                created_at=utc_now(),
            )
        )
        session.flush()
        jobs = (
            _add_job(session, context, project_id=other_project.id),
            _add_job(session, context, organization_id=other_organization_id),
            _add_job(session, context, job_type="material.parse"),
            _add_job(session, context, status="cancel_requested"),
            _add_job(session, context, status="succeeded"),
        )

    sink = SqlAlchemyAttemptAuditSink(factory)
    for index, job in enumerate(jobs):
        with pytest.raises(RuntimeError, match="generation job"):
            sink.start(
                replace(context, generation_job_id=job.id),
                _request(f"req-invalid-job-binding-{index}"),
                provider_name="provider-test",
                provider_model="model-test",
                route_reason="configured_primary",
            )

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(GenerationAttempt)) == 0


def test_historical_mismatched_jobs_cannot_cancel_attempts(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    other_organization_id = new_uuid7()
    with factory() as session, session.begin():
        other_project = ProjectRepository(session, _actor_for(context)).create(
            CreateProjectRequest(title="Wrong project", knowledge_point="One quarter")
        )
        session.add(
            Organization(
                id=other_organization_id,
                slug=f"wrong-{other_organization_id.hex[:12]}",
                name="Wrong organization",
                status="active",
                created_at=utc_now(),
            )
        )
        session.flush()
        wrong_project_job = _add_job(
            session,
            context,
            project_id=other_project.id,
            status="cancel_requested",
        )
        wrong_organization_job = _add_job(
            session,
            context,
            organization_id=other_organization_id,
            status="cancel_requested",
        )
        disallowed_job = _add_job(
            session,
            context,
            job_type="material.parse",
            status="cancel_requested",
        )
        attempts = (
            _add_running_attempt(
                session,
                context,
                attempt_no=1,
                request_id="req-history-wrong-project",
                generation_job_id=wrong_project_job.id,
            ),
            _add_running_attempt(
                session,
                context,
                attempt_no=2,
                request_id="req-history-wrong-organization",
                generation_job_id=wrong_organization_job.id,
            ),
            _add_running_attempt(
                session,
                context,
                attempt_no=3,
                request_id="req-history-disallowed-job",
                generation_job_id=disallowed_job.id,
            ),
        )
        attempt_ids = tuple(attempt.id for attempt in attempts)

    result = AttemptRecoveryCoordinator(factory).reconcile(limit=10)

    with factory() as session:
        persisted = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.id.in_(attempt_ids))
                .order_by(GenerationAttempt.attempt_no)
            )
        )
    assert result.cancellation_requests == 0
    assert all(attempt.cancel_requested_at is None for attempt in persisted)


def test_attempt_recovery_does_not_deadlock_with_job_cancel_lock(
    migrated_database_url: str,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    context = _seed_context(factory)
    with factory() as session, session.begin():
        job = _add_job(session, context)
    context = replace(context, generation_job_id=job.id)
    lease = SqlAlchemyAttemptAuditSink(factory).start(
        context,
        _request("req-cancel-lock-order"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        with factory() as session, session.begin():
            locked_job = session.get(GenerationJob, job.id, with_for_update=True)
            assert locked_job is not None
            locked_job.status = "cancel_requested"
            locked_job.cancel_requested_at = utc_now()
            session.flush()
            pending = executor.submit(AttemptRecoveryCoordinator(factory).reconcile, limit=1)
            assert pending.result(timeout=2).cancellation_requests == 0

    assert AttemptRecoveryCoordinator(factory).reconcile(limit=1).cancellation_requests == 1
    assert SqlAlchemyAttemptAuditSink(factory).heartbeat(lease, context) == (
        AttemptHeartbeat.CANCEL_REQUESTED
    )


def test_success_after_cancel_persists_real_usage_as_cancelled(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    sink = SqlAlchemyAttemptAuditSink(factory)
    lease = sink.start(
        context,
        _request("req-success-after-cancel"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )
    assert AttemptRecoveryCoordinator(factory).request_cancel(lease.attempt_id) is True

    outcome = sink.succeed(
        lease,
        context,
        AttemptSuccessAudit(
            provider_request_id="provider-completed-after-cancel",
            actual_model="model-actual",
            finish_reason="stop",
            usage=ModelUsage(
                prompt_tokens=11,
                completion_tokens=7,
                total_tokens=18,
                cost=Decimal("0.123456"),
                currency="USD",
            ),
        ),
        latency_ms=41,
    )

    with factory() as session:
        attempt = session.get(GenerationAttempt, lease.attempt_id)
        usage = session.scalar(
            select(UsageRecord).where(UsageRecord.generation_attempt_id == lease.attempt_id)
        )
    assert outcome.value == "cancelled"
    assert attempt is not None and attempt.status == "cancelled"
    assert attempt.error_code == GatewayErrorCode.CANCELLED.value
    assert attempt.provider_request_id == "provider-completed-after-cancel"
    assert usage is not None and usage.actual_cost == Decimal("0.123456")
    assert usage.input_units_json["prompt_tokens"] == 11
    assert usage.output_units_json["completion_tokens"] == 7


def test_committed_job_cancel_blocks_success_before_reconcile(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    with factory() as session, session.begin():
        job = _add_job(session, context)
    context = replace(context, generation_job_id=job.id)
    sink = SqlAlchemyAttemptAuditSink(factory)
    lease = sink.start(
        context,
        _request("req-job-cancel-before-success"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )

    with factory() as session, session.begin():
        persisted_job = session.get(GenerationJob, job.id, with_for_update=True)
        assert persisted_job is not None
        persisted_job.status = "cancel_requested"
        persisted_job.cancel_requested_at = utc_now()

    outcome = sink.succeed(
        lease,
        context,
        AttemptSuccessAudit(
            provider_request_id="provider-completed-after-job-cancel",
            actual_model="model-actual",
            finish_reason="stop",
            usage=ModelUsage(
                prompt_tokens=5,
                completion_tokens=3,
                total_tokens=8,
                cost=Decimal("0.010000"),
                currency="USD",
            ),
        ),
        latency_ms=17,
    )

    with factory() as session:
        attempt = session.get(GenerationAttempt, lease.attempt_id)
        usage = session.scalar(
            select(UsageRecord).where(UsageRecord.generation_attempt_id == lease.attempt_id)
        )
    assert outcome.value == "cancelled"
    assert attempt is not None and attempt.status == "cancelled"
    assert attempt.error_code == GatewayErrorCode.CANCELLED.value
    assert attempt.provider_request_id == "provider-completed-after-job-cancel"
    assert usage is not None and usage.actual_cost == Decimal("0.010000")


def test_committed_job_cancel_marks_failure_as_cancelled(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    with factory() as session, session.begin():
        job = _add_job(session, context)
    context = replace(context, generation_job_id=job.id)
    sink = SqlAlchemyAttemptAuditSink(factory)
    lease = sink.start(
        context,
        _request("req-job-cancel-before-failure"),
        provider_name="provider-test",
        provider_model="model-test",
        route_reason="configured_primary",
    )

    with factory() as session, session.begin():
        persisted_job = session.get(GenerationJob, job.id, with_for_update=True)
        assert persisted_job is not None
        persisted_job.status = "cancel_requested"
        persisted_job.cancel_requested_at = utc_now()

    sink.fail(
        lease,
        context,
        ModelGatewayError(GatewayErrorCode.PROVIDER_UNAVAILABLE, retryable=True),
        latency_ms=19,
    )

    with factory() as session:
        attempt = session.get(GenerationAttempt, lease.attempt_id)
    assert attempt is not None
    assert attempt.status == "cancelled"
    assert attempt.error_code == GatewayErrorCode.CANCELLED.value
    assert attempt.cancel_requested_at is not None


def test_recovery_clamps_long_latency_without_starving_same_batch(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    with factory() as session, session.begin():
        old_attempt = _add_running_attempt(
            session,
            context,
            attempt_no=1,
            request_id="req-expired-thirty-days",
            submitted_ago=timedelta(days=30),
            lease_expired=True,
        )
        recent_attempt = _add_running_attempt(
            session,
            context,
            attempt_no=2,
            request_id="req-expired-recent",
            submitted_ago=timedelta(minutes=1),
            lease_expired=True,
        )
        attempt_ids = (old_attempt.id, recent_attempt.id)

    result = AttemptRecoveryCoordinator(factory).reconcile(limit=2)

    with factory() as session:
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.id.in_(attempt_ids))
                .order_by(GenerationAttempt.attempt_no)
            )
        )
        usage_count = session.scalar(
            select(func.count())
            .select_from(UsageRecord)
            .where(UsageRecord.generation_attempt_id.in_(attempt_ids))
        )
    assert result.failed == 2
    assert [attempt.status for attempt in attempts] == ["failed", "failed"]
    assert attempts[0].latency_ms == 2_147_483_647
    assert attempts[1].latency_ms is not None and attempts[1].latency_ms < 2_147_483_647
    assert usage_count == 2


def test_cancellation_candidate_query_applies_limit_before_job_lookup(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    context = _seed_context(factory)
    with factory() as session, session.begin():
        for attempt_no in range(1, 4):
            job = _add_job(session, context, status="cancel_requested")
            _add_running_attempt(
                session,
                context,
                attempt_no=attempt_no,
                request_id=f"req-bounded-cancel-{attempt_no}",
                generation_job_id=job.id,
            )

    candidate_statements: list[str] = []
    reader_input_sizes: list[int] = []
    requested_bindings = GenerationJobCancellationReader.requested_bindings

    def capture_reader_input(
        self: GenerationJobCancellationReader,
        bindings: Collection[GenerationJobBinding],
    ) -> set[GenerationJobBinding]:
        reader_input_sizes.append(len(bindings))
        return requested_bindings(self, bindings)

    monkeypatch.setattr(
        GenerationJobCancellationReader,
        "requested_bindings",
        capture_reader_input,
    )

    @event.listens_for(engine, "before_cursor_execute")
    def capture_candidate_query(_conn, _cursor, statement, _parameters, _context, _many):
        normalized = " ".join(statement.split())
        if (
            "generation_attempts.generation_job_id" in normalized
            and "generation_attempts.cancel_requested_at IS NULL" in normalized
        ):
            candidate_statements.append(normalized)

    try:
        coordinator = AttemptRecoveryCoordinator(factory)
        first = coordinator.reconcile(limit=2)
        second = coordinator.reconcile(limit=2)
    finally:
        event.remove(engine, "before_cursor_execute", capture_candidate_query)

    assert first.cancellation_requests == 2
    assert second.cancellation_requests == 1
    assert candidate_statements
    assert all(" LIMIT " in statement.upper() for statement in candidate_statements)
    assert reader_input_sizes == [2, 1]


def test_cancellation_scan_advances_past_uncancelled_prefix(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    with factory() as session, session.begin():
        for attempt_no, minutes_ago in enumerate((4, 3, 2), start=1):
            job = _add_job(session, context)
            _add_running_attempt(
                session,
                context,
                attempt_no=attempt_no,
                request_id=f"req-cancel-fair-prefix-{attempt_no}",
                generation_job_id=job.id,
                submitted_ago=timedelta(minutes=minutes_ago),
            )
        cancelled_job = _add_job(session, context, status="cancel_requested")
        cancelled_attempt = _add_running_attempt(
            session,
            context,
            attempt_no=4,
            request_id="req-cancel-fair-tail",
            generation_job_id=cancelled_job.id,
            submitted_ago=timedelta(minutes=1),
        )

    coordinator = AttemptRecoveryCoordinator(factory)
    assert coordinator.reconcile(limit=2).cancellation_requests == 0
    assert coordinator.reconcile(limit=2).cancellation_requests == 1

    with factory() as session:
        persisted = session.get(GenerationAttempt, cancelled_attempt.id)
    assert persisted is not None and persisted.cancel_requested_at is not None

    with factory() as session, session.begin():
        wrapped_job = _add_job(session, context, status="cancel_requested")
        wrapped_attempt = _add_running_attempt(
            session,
            context,
            attempt_no=5,
            request_id="req-cancel-fair-wrap",
            generation_job_id=wrapped_job.id,
            submitted_ago=timedelta(minutes=5),
        )

    assert coordinator.reconcile(limit=2).cancellation_requests == 1
    with factory() as session:
        wrapped = session.get(GenerationAttempt, wrapped_attempt.id)
    assert wrapped is not None and wrapped.cancel_requested_at is not None


def test_cancellation_cursor_advances_only_after_transaction_commits(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    with factory() as session, session.begin():
        attempt_ids = []
        for attempt_no in range(1, 4):
            job = _add_job(session, context, status="cancel_requested")
            attempt = _add_running_attempt(
                session,
                context,
                attempt_no=attempt_no,
                request_id=f"req-cancel-rollback-{attempt_no}",
                generation_job_id=job.id,
            )
            attempt_ids.append(attempt.id)

    coordinator = AttemptRecoveryCoordinator(factory)

    def fail_after_coordination(_session: Session, *, limit: int) -> list[str]:
        raise RuntimeError(f"forced rollback after coordinating limit {limit}")

    with monkeypatch.context() as patch:
        patch.setattr(
            AttemptRecoveryCoordinator,
            "_recover_expired",
            staticmethod(fail_after_coordination),
        )
        with pytest.raises(RuntimeError, match="forced rollback"):
            coordinator.reconcile(limit=2)

    with factory() as session:
        rolled_back = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.id.in_(attempt_ids))
                .order_by(GenerationAttempt.attempt_no)
            )
        )
    assert all(attempt.cancel_requested_at is None for attempt in rolled_back)
    assert coordinator.reconcile(limit=2).cancellation_requests == 2


def test_restarted_coordinator_rescans_before_advancing_to_cancelled_tail(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    with factory() as session, session.begin():
        for attempt_no, minutes_ago in enumerate((3, 2), start=1):
            job = _add_job(session, context)
            _add_running_attempt(
                session,
                context,
                attempt_no=attempt_no,
                request_id=f"req-cancel-restart-prefix-{attempt_no}",
                generation_job_id=job.id,
                submitted_ago=timedelta(minutes=minutes_ago),
            )
        cancelled_job = _add_job(session, context, status="cancel_requested")
        cancelled_attempt = _add_running_attempt(
            session,
            context,
            attempt_no=3,
            request_id="req-cancel-restart-tail",
            generation_job_id=cancelled_job.id,
            submitted_ago=timedelta(minutes=1),
        )

    assert AttemptRecoveryCoordinator(factory).reconcile(limit=2).cancellation_requests == 0

    restarted = AttemptRecoveryCoordinator(factory)
    assert restarted.reconcile(limit=2).cancellation_requests == 0
    assert restarted.reconcile(limit=2).cancellation_requests == 1
    with factory() as session:
        persisted = session.get(GenerationAttempt, cancelled_attempt.id)
    assert persisted is not None and persisted.cancel_requested_at is not None


def test_shared_coordinator_serializes_cancellation_cursor(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    with factory() as session, session.begin():
        for attempt_no, minutes_ago in enumerate((4, 3, 2), start=1):
            job = _add_job(session, context)
            _add_running_attempt(
                session,
                context,
                attempt_no=attempt_no,
                request_id=f"req-cancel-shared-prefix-{attempt_no}",
                generation_job_id=job.id,
                submitted_ago=timedelta(minutes=minutes_ago),
            )
        cancelled_job = _add_job(session, context, status="cancel_requested")
        _add_running_attempt(
            session,
            context,
            attempt_no=4,
            request_id="req-cancel-shared-tail",
            generation_job_id=cancelled_job.id,
            submitted_ago=timedelta(minutes=1),
        )

    coordinator = AttemptRecoveryCoordinator(factory)
    barrier = Barrier(2)

    def reconcile(_index: int):
        barrier.wait()
        return coordinator.reconcile(limit=2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reconcile, (1, 2)))

    assert sum(result.cancellation_requests for result in results) == 1


def test_independent_coordinators_apply_disjoint_cancellation_batches(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    context = _seed_context(factory)
    with factory() as session, session.begin():
        attempt_ids = []
        for attempt_no in range(1, 5):
            job = _add_job(session, context, status="cancel_requested")
            attempt = _add_running_attempt(
                session,
                context,
                attempt_no=attempt_no,
                request_id=f"req-cancel-independent-{attempt_no}",
                generation_job_id=job.id,
            )
            attempt_ids.append(attempt.id)

    barrier = Barrier(2)

    def reconcile(_index: int):
        barrier.wait()
        return AttemptRecoveryCoordinator(factory).reconcile(limit=2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reconcile, (1, 2)))

    with factory() as session:
        persisted = list(
            session.scalars(select(GenerationAttempt).where(GenerationAttempt.id.in_(attempt_ids)))
        )
    assert sum(result.cancellation_requests for result in results) == 4
    assert all(attempt.cancel_requested_at is not None for attempt in persisted)


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

    with pytest.raises(IntegrityError) as captured, factory() as session, session.begin():
        session.add(_usage_record(lease.attempt_id, context))
        session.flush()
    assert getattr(captured.value.orig, "sqlstate", None) == "23514"


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
