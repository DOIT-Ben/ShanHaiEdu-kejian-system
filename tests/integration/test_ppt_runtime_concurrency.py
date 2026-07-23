from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

from sqlalchemy import select

from apps.api.artifacts.models import ArtifactVersion
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.ppt_rendering.models import AssemblyManifest, AssemblyRequest, PptxFileFact
from apps.api.ppt_rendering.service import assemble_pages, export_pptx
from apps.api.ppt_runtime.contracts import PptRuntimeError
from apps.api.ppt_runtime.service import PptRuntimeService
from apps.api.ppt_runtime.sqlalchemy import SqlAlchemyPptRuntimeTransactionFactory
from apps.api.workflows.models import NodeExecutionLease, NodeRun
from tests.fakes.object_storage import FakeObjectStorage
from tests.integration.ppt_runtime_support import count_for_node, seed_ppt
from workflow.node_state import NodeStatus


class _BlockingRenderer:
    def __init__(self, entered: Event, release: Event) -> None:
        self._entered = entered
        self._release = release

    def assemble_pages(self, request: AssemblyRequest) -> AssemblyManifest:
        self._entered.set()
        if not self._release.wait(timeout=30):
            raise TimeoutError("blocking PPT renderer was not released")
        return assemble_pages(request)

    def export_pptx(self, request: AssemblyRequest) -> PptxFileFact:
        return export_pptx(request)


class _LoseLeasesRenderer:
    def __init__(self, lose: Callable[[], None]) -> None:
        self._lose = lose

    def assemble_pages(self, request: AssemblyRequest) -> AssemblyManifest:
        result = assemble_pages(request)
        self._lose()
        return result

    def export_pptx(self, request: AssemblyRequest) -> PptxFileFact:
        return export_pptx(request)


def test_concurrent_delivery_keeps_first_owner_and_one_effective_result(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)
    entered = Event()
    release = Event()
    service = PptRuntimeService(
        SqlAlchemyPptRuntimeTransactionFactory(factory, seeded.actor),
        storage,
        storage_bucket="shanhaiedu",
        renderer=_BlockingRenderer(entered, release),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            service.execute,
            seeded.assemble_node_id,
            request_id="issue-170-concurrent",
        )
        assert entered.wait(timeout=30)
        try:
            service.execute(
                seeded.assemble_node_id,
                request_id="issue-170-concurrent",
            )
        except PptRuntimeError as exc:
            rejected_code = exc.code
        else:
            raise AssertionError("concurrent PPT execution unexpectedly acquired the owner")
        finally:
            release.set()
        committed = first_future.result(timeout=60)

    assert rejected_code == "NODE_EXECUTION_IN_FLIGHT"
    with factory() as session:
        node = session.get(NodeRun, seeded.assemble_node_id)
        assert node is not None and node.status == NodeStatus.APPROVED.value
        assert node.active_artifact_version_id == committed.artifact_version_id
        assert count_for_node(session, GenerationAttempt, node.id) == 1
        assert count_for_node(session, UsageRecord, node.id) == 1
        versions = list(
            session.scalars(
                select(ArtifactVersion).where(ArtifactVersion.source_node_run_id == node.id)
            )
        )
        assert [version.id for version in versions] == [committed.artifact_version_id]


def test_lost_attempt_and_node_owners_cannot_commit_and_recover_once(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    storage = FakeObjectStorage()
    seeded = seed_ppt(factory, storage)

    def replace_owners() -> None:
        with factory() as session, session.begin():
            node_lease = session.get(NodeExecutionLease, seeded.assemble_node_id)
            attempt = session.scalar(
                select(GenerationAttempt).where(
                    GenerationAttempt.node_run_id == seeded.assemble_node_id,
                    GenerationAttempt.status == "running",
                )
            )
            assert node_lease is not None and attempt is not None
            replacement_identity = "replacement-worker"
            node_lease.owner_token = replacement_identity
            attempt.lease_owner = replacement_identity

    stale_service = PptRuntimeService(
        SqlAlchemyPptRuntimeTransactionFactory(factory, seeded.actor),
        storage,
        storage_bucket="shanhaiedu",
        renderer=_LoseLeasesRenderer(replace_owners),
    )
    try:
        stale_service.execute(
            seeded.assemble_node_id,
            request_id="issue-170-expired-owner",
        )
    except PptRuntimeError as exc:
        assert exc.code == "PPT_RUNTIME_OWNER_LOST"
    else:
        raise AssertionError("expired PPT worker unexpectedly committed")

    with factory() as session:
        node = session.get(NodeRun, seeded.assemble_node_id)
        attempt = session.scalar(
            select(GenerationAttempt).where(
                GenerationAttempt.node_run_id == seeded.assemble_node_id
            )
        )
        assert node is not None and node.status == NodeStatus.RUNNING.value
        assert attempt is not None and attempt.status == "running"
        assert count_for_node(session, UsageRecord, node.id) == 0
        assert count_for_node(session, GenerationAttempt, node.id) == 1

    with factory() as session, session.begin():
        node_lease = session.get(NodeExecutionLease, seeded.assemble_node_id)
        attempt = session.scalar(
            select(GenerationAttempt).where(
                GenerationAttempt.node_run_id == seeded.assemble_node_id,
                GenerationAttempt.status == "running",
            )
        )
        assert node_lease is not None and attempt is not None
        heartbeat_at = utc_now()
        expired_at = heartbeat_at + timedelta(microseconds=1)
        node_lease.lease_expires_at = expired_at
        attempt.heartbeat_at = heartbeat_at
        attempt.lease_expires_at = expired_at

    recovered = PptRuntimeService(
        SqlAlchemyPptRuntimeTransactionFactory(factory, seeded.actor),
        storage,
        storage_bucket="shanhaiedu",
    ).execute(
        seeded.assemble_node_id,
        request_id="issue-170-expired-owner",
    )

    with factory() as session:
        node = session.get(NodeRun, seeded.assemble_node_id)
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.node_run_id == seeded.assemble_node_id)
                .order_by(GenerationAttempt.attempt_no)
            )
        )
        assert node is not None and node.status == NodeStatus.APPROVED.value
        assert node.active_artifact_version_id == recovered.artifact_version_id
        assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]
        assert count_for_node(session, UsageRecord, node.id) == 2
