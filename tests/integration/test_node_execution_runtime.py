from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.domain import canonical_content_hash
from apps.api.artifacts.execution_port import ArtifactExecutionPortError, SqlAlchemyArtifactPort
from apps.api.artifacts.models import Artifact, ArtifactRelation, ArtifactVersion
from apps.api.artifacts.relation_service import ArtifactRelationService
from apps.api.assets.models import FileAsset, FileAssetVersion, MaterialParseVersion
from apps.api.assets.project_models import ProjectAssetSlot
from apps.api.content_runtime.models import ContentDefinitionVersion
from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.creation.models import CreationPackage, CreationPackageItem
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.context import ActorContext
from apps.api.ids import new_uuid7
from apps.api.lessons.models import LessonUnit
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import ModelCapability, TextModelRequest, TextProviderResult
from apps.api.model_gateway.fake import DeterministicFakeTextProvider, FakeScenario
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.node_execution.contracts import NodeExecutionError, PreparedNodeExecution
from apps.api.node_execution.fake import DeterministicNodeOutputProvider
from apps.api.node_execution.materials import collect_upstream_artifacts
from apps.api.node_execution.models import NodeExecutionRecoveryFact
from apps.api.node_execution.prompt_plan import NodePromptPlanError
from apps.api.node_execution.service import NodeExecutionService
from apps.api.node_execution.sqlalchemy import SqlAlchemyNodeExecutionTransactionFactory
from apps.api.node_execution.structured_output import validate_structured_output
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.prompt_runtime.models import ContextSnapshot, PromptSnapshot
from apps.api.runtime_boundary.output_projection import compile_output_projection
from apps.api.runtime_boundary.ports import WorkflowExecutionContext
from apps.api.uploads.models import SourceMaterial
from apps.api.workflows.execution_port import WorkflowExecutionPortError
from apps.api.workflows.models import (
    BranchRun,
    NodeExecutionLease,
    NodeInputSnapshot,
    NodeRun,
    WorkflowRun,
)
from apps.api.workflows.service import WorkflowRuntimeService
from scripts.golden_courseware_branch_inputs import build_golden_branch_source_outputs
from tests.fakes.identity import seed_test_actor
from workers.recovery import WorkerRecoveryCoordinator
from workflow.node_state import NodeStatus

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CASE_PATH = ROOT / "contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json"


@dataclass(frozen=True, slots=True)
class RuntimeSeed:
    actor: ActorContext
    project_id: UUID
    workflow_run_id: UUID
    node_run_id: UUID
    upstream_version_id: UUID
    output: dict[str, object]


@pytest.mark.parametrize(
    "field",
    [
        "node_run_id",
        "context_snapshot_id",
        "prompt_snapshot_id",
        "content_definition_version_id",
    ],
)
def test_generated_artifact_capability_rejects_forged_execution_provenance(
    migrated_database_url: str,
    field: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions = SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor)
    with transactions.begin() as transaction:
        prepared = transaction.prepare(seeded.node_run_id, f"issue-131-{field}")
    context = prepared.commit_context
    assert context is not None
    plan = compile_output_projection(
        definition=context.definition,
        execution=context.execution,
        snapshots=context.snapshots,
        validated_output=seeded.output,
        upstream_artifacts=context.upstream_artifacts,
        request_id=prepared.request.request_id,
        runtime_values=context.runtime_values,
        target_slot_authorization=context.target_slot_authorization,
        reference_asset_authorization=context.reference_asset_authorization,
    )
    forged = replace(plan.artifact_write, **{field: new_uuid7()})

    with factory() as session, session.begin():
        with pytest.raises(ArtifactExecutionPortError) as caught:
            SqlAlchemyArtifactPort(session, seeded.actor).persist_generated(forged)
        assert caught.value.code == "NODE_EXECUTION_ARTIFACT_PROVENANCE_INVALID"
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0


async def test_published_golden_text_node_commits_complete_lineage_once(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    provider = DeterministicNodeOutputProvider(seeded.output)
    gateway = ModelGateway(
        {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        gateway,
    )

    first = await service.execute(
        seeded.node_run_id,
        request_id="issue-89-golden-delivery",
    )
    replay = await service.execute(
        seeded.node_run_id,
        request_id="issue-89-golden-delivery",
    )
    with pytest.raises(WorkflowExecutionPortError) as conflict:
        await service.execute(
            seeded.node_run_id,
            request_id="issue-89-different-delivery",
        )

    assert replay == first
    assert conflict.value.code == "NODE_EXECUTION_IDEMPOTENCY_CONFLICT"
    assert provider.calls == 1
    assert first.creation_package_id is None
    assert first.attempt_id is not None
    assert first.usage_id is not None
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        artifact_version = session.get(ArtifactVersion, first.artifact_version_id)
        assert artifact_version is not None
        artifact = session.get(Artifact, artifact_version.artifact_id)
        context = session.scalar(
            select(ContextSnapshot).where(ContextSnapshot.node_run_id == seeded.node_run_id)
        )
        prompt = session.scalar(
            select(PromptSnapshot).where(PromptSnapshot.node_run_id == seeded.node_run_id)
        )
        frozen = session.scalar(
            select(NodeInputSnapshot).where(
                NodeInputSnapshot.node_run_id == seeded.node_run_id,
                NodeInputSnapshot.input_key == "runtime.execution",
            )
        )
        attempt = session.get(GenerationAttempt, first.attempt_id)
        usage = session.get(UsageRecord, first.usage_id)
        relation = session.scalar(
            select(ArtifactRelation).where(
                ArtifactRelation.to_artifact_version_id == first.artifact_version_id
            )
        )

        assert node is not None
        assert node.status == NodeStatus.REVIEW_REQUIRED.value
        assert node.active_artifact_version_id == first.artifact_version_id
        assert artifact_version.content_json == seeded.output
        assert artifact_version.source_node_run_id == seeded.node_run_id
        assert artifact is not None
        assert artifact.artifact_key == "lesson-division"
        assert artifact.artifact_type == "lesson_division"
        assert context is not None
        assert prompt is not None
        assert prompt.context_snapshot_id == context.id
        assert artifact_version.context_snapshot_id == context.id
        assert artifact_version.prompt_snapshot_id == prompt.id
        assert frozen is not None
        assert frozen.snapshot_json["request_id"] == "issue-89-golden-delivery"
        assert frozen.snapshot_json["reference_assets"] == []
        assert attempt is not None
        assert attempt.status == "succeeded"
        assert attempt.node_run_id == seeded.node_run_id
        assert usage is not None
        assert usage.generation_attempt_id == attempt.id
        assert usage.node_run_id == seeded.node_run_id
        assert relation is not None
        assert relation.from_artifact_version_id == seeded.upstream_version_id
        assert relation.binding_key == "upstream.approval.material_scope"
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 1
        assert _count(session, GenerationAttempt, "node_run_id", seeded.node_run_id) == 1
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 1


@dataclass(frozen=True, slots=True)
class _Cancelled:
    cancelled: bool = True


class _CancelBeforeCommitProvider(DeterministicNodeOutputProvider):
    def __init__(self, output: dict[str, object], cancel: Callable[[], None]) -> None:
        super().__init__(output)
        self._cancel = cancel

    async def complete(self, request: TextModelRequest) -> TextProviderResult:
        result = await super().complete(request)
        self._cancel()
        return result


async def test_cancelled_node_has_no_attempt_or_artifact(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )

    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(
            seeded.node_run_id,
            request_id="issue-89-cancelled",
            cancellation=_Cancelled(),
        )

    assert caught.value.code == "MODEL_CANCELLED"
    assert provider.calls == 0
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.CANCELLED.value
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0
        assert _count(session, GenerationAttempt, "node_run_id", seeded.node_run_id) == 0
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 0


async def test_cancel_requested_before_execution_terminalizes_without_provider(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    with factory() as session, session.begin():
        runtime = WorkflowRuntimeService(session, seeded.actor)
        runtime.transition_node(seeded.node_run_id, NodeStatus.QUEUED)
        runtime.transition_node(seeded.node_run_id, NodeStatus.CANCEL_REQUESTED)

    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(seeded.node_run_id, request_id="issue-89-precancelled")

    assert caught.value.code == "NODE_EXECUTION_CANCEL_REQUESTED"
    assert provider.calls == 0
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.CANCELLED.value
        assert _count(session, GenerationAttempt, "node_run_id", seeded.node_run_id) == 0
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 0
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0
        assert _count(session, PromptSnapshot, "node_run_id", seeded.node_run_id) == 0
        assert _count(session, ContextSnapshot, "node_run_id", seeded.node_run_id) == 0


async def test_cancel_requested_before_recovery_discards_fact_without_provider(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions, _ = await _checkpoint_recovery_fact(
        factory,
        seeded,
        "issue-89-precancelled-recovery",
    )
    with factory() as session, session.begin():
        WorkflowRuntimeService(session, seeded.actor).transition_node(
            seeded.node_run_id,
            NodeStatus.CANCEL_REQUESTED,
        )

    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        transactions,
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(
            seeded.node_run_id,
            request_id="issue-89-precancelled-recovery",
        )

    assert caught.value.code == "NODE_EXECUTION_CANCEL_REQUESTED"
    assert provider.calls == 0
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.CANCELLED.value
        assert _count(session, GenerationAttempt, "node_run_id", seeded.node_run_id) == 1
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 1
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 0
        assert session.get(NodeExecutionLease, seeded.node_run_id) is None


async def test_cancel_requested_after_model_success_rolls_back_t2(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)

    def cancel() -> None:
        with factory() as session, session.begin():
            WorkflowRuntimeService(session, seeded.actor).transition_node(
                seeded.node_run_id,
                NodeStatus.CANCEL_REQUESTED,
            )

    provider = _CancelBeforeCommitProvider(seeded.output, cancel)
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )

    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(seeded.node_run_id, request_id="issue-89-cancel-before-t2")

    assert caught.value.code == "NODE_EXECUTION_CANCEL_REQUESTED"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.CANCELLED.value
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0
        assert _count(session, GenerationAttempt, "node_run_id", seeded.node_run_id) == 1
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 1
        attempt = session.scalar(
            select(GenerationAttempt).where(GenerationAttempt.node_run_id == seeded.node_run_id)
        )
        assert attempt is not None and attempt.status == "cancelled"
        usage = session.scalar(
            select(UsageRecord).where(UsageRecord.generation_attempt_id == attempt.id)
        )
        assert usage is not None
        assert usage.input_units_json["prompt_tokens"] == 8
        assert usage.output_units_json["completion_tokens"] == 4
        assert usage.output_units_json["total_tokens"] == 12
        assert usage.actual_cost == 0
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 0


async def test_invalid_output_records_known_usage_without_artifact(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    provider = DeterministicNodeOutputProvider({"unexpected": True})
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )

    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(seeded.node_run_id, request_id="issue-89-invalid-output-usage")

    assert caught.value.code == "MODEL_OUTPUT_SCHEMA_INVALID"
    with factory() as session:
        attempt = session.scalar(
            select(GenerationAttempt).where(GenerationAttempt.node_run_id == seeded.node_run_id)
        )
        assert attempt is not None and attempt.status == "failed"
        usage = session.scalar(
            select(UsageRecord).where(UsageRecord.generation_attempt_id == attempt.id)
        )
        assert usage is not None
        assert usage.input_units_json["prompt_tokens"] == 8
        assert usage.output_units_json["completion_tokens"] == 4
        assert usage.output_units_json["total_tokens"] == 12
        assert usage.actual_cost == 0
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 0


@pytest.mark.parametrize("fault_stage", ["after_artifact", "after_package", "before_transition"])
async def test_t2_failure_rolls_back_artifact_and_relations(
    migrated_database_url: str,
    fault_stage: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    provider = DeterministicNodeOutputProvider(seeded.output)

    def fail(stage: str) -> None:
        if stage == fault_stage:
            raise RuntimeError(f"fault injected at {stage}")

    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(
            factory,
            seeded.actor,
            fault_injector=fail,
        ),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )

    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(seeded.node_run_id, request_id=f"issue-89-t2-{fault_stage}")

    assert caught.value.code == "NODE_EXECUTION_COMMIT_FAILED"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(ArtifactRelation)
                .join(
                    ArtifactVersion,
                    ArtifactVersion.id == ArtifactRelation.to_artifact_version_id,
                )
                .where(ArtifactVersion.source_node_run_id == seeded.node_run_id)
            )
            == 0
        )
        assert _count(session, GenerationAttempt, "node_run_id", seeded.node_run_id) == 1
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 1


async def test_concurrent_delivery_has_one_effective_model_execution(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )

    results = await asyncio.gather(
        service.execute(seeded.node_run_id, request_id="issue-89-concurrent"),
        service.execute(seeded.node_run_id, request_id="issue-89-concurrent"),
        return_exceptions=True,
    )

    committed = [item for item in results if not isinstance(item, Exception)]
    rejected = [item for item in results if isinstance(item, NodeExecutionError)]
    assert len(committed) == 1
    assert len(rejected) == 1
    assert rejected[0].code == "NODE_EXECUTION_IN_FLIGHT"
    assert provider.calls == 1
    with factory() as session:
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 1
        assert _count(session, GenerationAttempt, "node_run_id", seeded.node_run_id) == 1
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 1


async def test_worker_recovery_after_t1_does_not_repeat_provider_call(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions = SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor)
    with transactions.begin() as transaction:
        prepared = transaction.prepare(seeded.node_run_id, "issue-89-recover")
        assert prepared.committed_result is None
    with factory() as session, session.begin():
        lease = session.get(NodeExecutionLease, seeded.node_run_id)
        assert lease is not None
        lease.lease_expires_at = utc_now() - timedelta(seconds=1)

    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        transactions,
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    result = await service.execute(seeded.node_run_id, request_id="issue-89-recover")

    assert result.attempt_id is not None
    assert provider.calls == 1
    with factory() as session:
        assert _count(session, GenerationAttempt, "node_run_id", seeded.node_run_id) == 1
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 1


async def test_worker_recovery_after_t1_uses_frozen_prompt_before_upstream_stale(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions = SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor)
    with transactions.begin() as transaction:
        transaction.prepare(seeded.node_run_id, "issue-89-recover-frozen-stale")
    with factory() as session, session.begin():
        source = session.get(ArtifactVersion, seeded.upstream_version_id)
        lease = session.get(NodeExecutionLease, seeded.node_run_id)
        assert source is not None and lease is not None
        replacement = ArtifactVersion(
            id=new_uuid7(),
            organization_id=seeded.actor.organization_id,
            artifact_id=source.artifact_id,
            version_no=2,
            content_json={"replacement": True},
            content_hash=canonical_content_hash({"replacement": True}),
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=seeded.actor.principal_id,
        )
        session.add(replacement)
        session.flush()
        artifact = session.get(Artifact, source.artifact_id)
        assert artifact is not None
        artifact.current_approved_version_id = replacement.id
        lease.lease_expires_at = utc_now() - timedelta(seconds=1)

    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        transactions,
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(
            seeded.node_run_id,
            request_id="issue-89-recover-frozen-stale",
        )

    assert caught.value.code == "NODE_EXECUTION_UPSTREAM_STALE"
    assert provider.calls == 1
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0


async def test_successful_attempt_before_t2_recovers_from_isolated_fact_without_second_attempt(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions = SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor)
    with transactions.begin() as transaction:
        prepared = transaction.prepare(seeded.node_run_id, "issue-89-lost-t2")

    gateway = ModelGateway(
        {
            ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: DeterministicNodeOutputProvider(
                seeded.output
            )
        },
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    pending = await gateway.generate_text_pending(
        prepared.request,
        audit_context=prepared.audit_context,
    )
    output = validate_structured_output(pending.result.text, prepared.output_schema)
    with transactions.begin() as transaction:
        transaction.checkpoint(prepared, output, pending)
    with factory() as session, session.begin():
        lease = session.get(NodeExecutionLease, seeded.node_run_id)
        assert lease is not None
        lease.lease_expires_at = utc_now() - timedelta(seconds=1)

    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        transactions,
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    result = await service.execute(seeded.node_run_id, request_id="issue-89-lost-t2")

    assert result.attempt_id is not None
    assert provider.calls == 0
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 0
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 1
        assert _count(session, GenerationAttempt, "node_run_id", seeded.node_run_id) == 1
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 1


async def test_t2_rollback_keeps_isolated_recovery_fact_for_retry(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    calls = {"count": 0}

    def fault(stage: str) -> None:
        if stage == "after_artifact":
            raise RuntimeError("test T2 rollback")

    first_service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor, fault_injector=fault),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: DeterministicNodeOutputProvider(
                    seeded.output
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodeExecutionError):
        await first_service.execute(seeded.node_run_id, request_id="issue-89-recovery-rollback")

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 1

    class CountingProvider(DeterministicNodeOutputProvider):
        async def complete(self, request):
            calls["count"] += 1
            return await super().complete(request)

    retry_service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: CountingProvider(seeded.output)},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    result = await retry_service.execute(
        seeded.node_run_id, request_id="issue-89-recovery-rollback"
    )
    assert result.attempt_id is not None
    assert calls["count"] == 0


async def test_checkpoint_failure_rolls_back_attempt_usage_and_recovery_fact(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)

    def fault(stage: str) -> None:
        if stage == "after_recovery_fact":
            raise RuntimeError("test checkpoint rollback")

    transactions = SqlAlchemyNodeExecutionTransactionFactory(
        factory,
        seeded.actor,
        fault_injector=fault,
    )
    with transactions.begin() as transaction:
        prepared = transaction.prepare(seeded.node_run_id, "issue-89-checkpoint-rollback")
    gateway = ModelGateway(
        {
            ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: DeterministicNodeOutputProvider(
                seeded.output
            )
        },
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    pending = await gateway.generate_text_pending(
        prepared.request,
        audit_context=prepared.audit_context,
    )
    output = validate_structured_output(pending.result.text, prepared.output_schema)

    with pytest.raises(RuntimeError, match="checkpoint rollback"):
        with transactions.begin() as transaction:
            transaction.checkpoint(prepared, output, pending)

    with factory() as session:
        attempt = session.scalar(
            select(GenerationAttempt).where(GenerationAttempt.node_run_id == seeded.node_run_id)
        )
        assert attempt is not None and attempt.status == "running"
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 0
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 0


async def test_service_checkpoint_failure_records_known_usage_once(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)

    def fault(stage: str) -> None:
        if stage == "after_recovery_fact":
            raise RuntimeError("test service checkpoint rollback")

    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(
            factory,
            seeded.actor,
            fault_injector=fault,
        ),
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(seeded.output)
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )

    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(
            seeded.node_run_id,
            request_id="issue-89-service-checkpoint-usage",
        )

    assert caught.value.code == "NODE_EXECUTION_CHECKPOINT_FAILED"
    with factory() as session:
        attempt = session.scalar(
            select(GenerationAttempt).where(GenerationAttempt.node_run_id == seeded.node_run_id)
        )
        assert attempt is not None and attempt.status == "failed"
        usage = session.scalar(
            select(UsageRecord).where(UsageRecord.generation_attempt_id == attempt.id)
        )
        assert usage is not None
        assert usage.input_units_json["prompt_tokens"] == 8
        assert usage.output_units_json["completion_tokens"] == 4
        assert usage.output_units_json["total_tokens"] == 12
        assert usage.actual_cost == 0
        assert _count(session, UsageRecord, "node_run_id", seeded.node_run_id) == 1
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 0


async def test_tampered_recovery_fact_is_rejected_without_provider_replay(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions = SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor)
    with transactions.begin() as transaction:
        prepared = transaction.prepare(seeded.node_run_id, "issue-89-tampered-recovery")
    gateway = ModelGateway(
        {
            ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: DeterministicNodeOutputProvider(
                seeded.output
            )
        },
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    pending = await gateway.generate_text_pending(
        prepared.request,
        audit_context=prepared.audit_context,
    )
    output = validate_structured_output(pending.result.text, prepared.output_schema)
    with transactions.begin() as transaction:
        transaction.checkpoint(prepared, output, pending)
    with factory() as session, session.begin():
        fact = session.scalar(select(NodeExecutionRecoveryFact).with_for_update())
        lease = session.get(NodeExecutionLease, seeded.node_run_id)
        assert fact is not None and lease is not None
        fact.output_hash = "0" * 64
        lease.lease_expires_at = utc_now() - timedelta(seconds=1)

    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        transactions,
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(seeded.node_run_id, request_id="issue-89-tampered-recovery")
    assert caught.value.code == "NODE_EXECUTION_RECOVERY_MISMATCH"
    assert provider.calls == 0


async def test_expired_recovery_fact_fails_closed_without_provider_replay(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions, _ = await _checkpoint_recovery_fact(
        factory,
        seeded,
        "issue-89-expired-recovery",
    )
    with factory() as session, session.begin():
        fact = session.scalar(select(NodeExecutionRecoveryFact).with_for_update())
        lease = session.get(NodeExecutionLease, seeded.node_run_id)
        assert fact is not None and lease is not None
        fact.expires_at = utc_now() - timedelta(seconds=1)
        lease.lease_expires_at = utc_now() - timedelta(seconds=1)

    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        transactions,
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(seeded.node_run_id, request_id="issue-89-expired-recovery")
    assert caught.value.code == "NODE_EXECUTION_RECOVERY_EXPIRED"
    assert provider.calls == 0
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 0


async def test_abandoned_recovery_fact_is_removed_by_retention_sweep(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    await _checkpoint_recovery_fact(factory, seeded, "issue-89-abandoned-retention")
    with factory() as session, session.begin():
        fact = session.scalar(select(NodeExecutionRecoveryFact).with_for_update())
        assert fact is not None
        fact.expires_at = utc_now() - timedelta(seconds=1)

    coordinator = WorkerRecoveryCoordinator(factory)
    assert coordinator.reconcile(limit=10).expired_recovery_facts == 1
    assert coordinator.reconcile(limit=10).expired_recovery_facts == 0
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 0
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0


async def test_recovery_fact_expiring_between_prepare_and_t2_is_deleted(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions, _ = await _checkpoint_recovery_fact(
        factory,
        seeded,
        "issue-89-expire-during-t2",
    )
    with factory() as session, session.begin():
        lease = session.get(NodeExecutionLease, seeded.node_run_id)
        assert lease is not None
        lease.lease_expires_at = utc_now() - timedelta(seconds=1)
    with transactions.begin() as transaction:
        recovered = transaction.prepare(seeded.node_run_id, "issue-89-expire-during-t2")
    with factory() as session, session.begin():
        fact = session.scalar(select(NodeExecutionRecoveryFact).with_for_update())
        assert fact is not None
        fact.expires_at = utc_now() - timedelta(seconds=1)

    service = NodeExecutionService(
        transactions,
        ModelGateway(
            {
                ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: (
                    DeterministicNodeOutputProvider(seeded.output)
                )
            },
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodeExecutionError) as caught:
        service._commit(recovered)

    assert caught.value.code == "NODE_EXECUTION_RECOVERY_EXPIRED"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert session.scalar(select(func.count()).select_from(NodeExecutionRecoveryFact)) == 0
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0


async def test_frozen_upstream_change_blocks_recovery_t2(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions, prepared = await _checkpoint_recovery_fact(
        factory,
        seeded,
        "issue-89-upstream-stale-before-t2",
    )
    with factory() as session, session.begin():
        source = session.get(ArtifactVersion, seeded.upstream_version_id)
        assert source is not None
        replacement = ArtifactVersion(
            id=new_uuid7(),
            organization_id=seeded.actor.organization_id,
            artifact_id=source.artifact_id,
            version_no=2,
            content_json={"replacement": True},
            content_hash=canonical_content_hash({"replacement": True}),
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=seeded.actor.principal_id,
        )
        session.add(replacement)
        session.flush()
        artifact = session.get(Artifact, source.artifact_id)
        assert artifact is not None
        artifact.current_approved_version_id = replacement.id
    with pytest.raises(ArtifactExecutionPortError) as caught:
        with transactions.begin() as transaction:
            transaction.commit(prepared)
    assert caught.value.code == "NODE_EXECUTION_UPSTREAM_STALE"
    with factory() as session:
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0


async def test_recovery_uses_frozen_inputs_then_rejects_changed_upstream(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions, _ = await _checkpoint_recovery_fact(
        factory,
        seeded,
        "issue-89-real-recovery-upstream-stale",
    )
    with factory() as session, session.begin():
        source = session.get(ArtifactVersion, seeded.upstream_version_id)
        lease = session.get(NodeExecutionLease, seeded.node_run_id)
        assert source is not None and lease is not None
        replacement = ArtifactVersion(
            id=new_uuid7(),
            organization_id=seeded.actor.organization_id,
            artifact_id=source.artifact_id,
            version_no=2,
            content_json={"replacement": True},
            content_hash=canonical_content_hash({"replacement": True}),
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=seeded.actor.principal_id,
        )
        session.add(replacement)
        session.flush()
        artifact = session.get(Artifact, source.artifact_id)
        assert artifact is not None
        artifact.current_approved_version_id = replacement.id
        lease.lease_expires_at = utc_now() - timedelta(seconds=1)

    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        transactions,
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodeExecutionError) as caught:
        await service.execute(
            seeded.node_run_id,
            request_id="issue-89-real-recovery-upstream-stale",
        )

    assert caught.value.code == "NODE_EXECUTION_UPSTREAM_STALE"
    assert provider.calls == 0
    with factory() as session:
        assert _count(session, ArtifactVersion, "source_node_run_id", seeded.node_run_id) == 0


async def test_lesson_scoped_context_and_relations_stay_with_current_lesson(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    with factory() as session, session.begin():
        run = session.get(WorkflowRun, seeded.workflow_run_id)
        assert run is not None
        definition_id = session.scalar(select(ContentDefinitionVersion.id).limit(1))
        assert definition_id is not None
        lessons = []
        for index in (1, 2):
            lesson = LessonUnit(
                id=new_uuid7(),
                organization_id=seeded.actor.organization_id,
                project_id=seeded.project_id,
                lesson_key=f"LESSON-{index:03d}",
                position=index,
                title=f"Lesson {index}",
                scope_summary="scope",
                objective_summary="objective",
                estimated_minutes=40,
                source_division_version_id=seeded.upstream_version_id,
                status="active",
                created_by=seeded.actor.principal_id,
                updated_by=seeded.actor.principal_id,
            )
            session.add(lesson)
            session.flush()
            _seed_approved_artifact(
                session,
                seeded.actor,
                seeded.project_id,
                definition_id,
                artifact_key=f"lesson-plan:{index}",
                artifact_type="lesson_plan",
                branch_key="lesson_plan",
                lesson_unit_id=lesson.id,
                content={"lesson_key": lesson.lesson_key},
            )
            lessons.append(lesson)

        _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            definition_id,
            artifact_key="lesson-plan:wrong-branch",
            artifact_type="lesson_plan",
            branch_key="ppt",
            lesson_unit_id=lessons[0].id,
        )
        project_division = _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            definition_id,
            artifact_key="lesson-division:project",
            artifact_type="lesson_division",
            branch_key="project",
            lesson_unit_id=None,
        )

        base = dict(
            organization_id=seeded.actor.organization_id,
            project_id=seeded.project_id,
            workflow_run_id=seeded.workflow_run_id,
            node_run_id=seeded.node_run_id,
            content_release_id=run.content_release_id,
            workflow_definition_version_id=run.workflow_definition_version_id,
            node_key="ppt.outline.generate",
            branch_key="ppt",
            lesson_key=lessons[0].lesson_key,
            status=NodeStatus.READY.value,
        )
        context = WorkflowExecutionContext(lesson_unit_id=lessons[0].id, **base)
        port = SqlAlchemyArtifactPort(session, seeded.actor)
        values = port.list_context_versions(context, "lesson_plan.approved_version")
        upstream = collect_upstream_artifacts(
            port, context, {"input_contract_refs": ["approval:lesson_plan"]}
        )
        assert [value.lesson_unit_id for value in values] == [lessons[0].id]
        assert upstream["approval:lesson_plan"].lesson_unit_id == lessons[0].id
        project_values = port.list_context_versions(
            context,
            "lesson_division.approved_version",
        )
        assert [value.artifact_version_id for value in project_values] == [project_division.id]
        with pytest.raises(ArtifactExecutionPortError) as caught:
            port.list_context_versions(context, "approval:undeclared")
        assert caught.value.code == "NODE_EXECUTION_CONTEXT_SOURCE_UNKNOWN"


async def test_prepare_claims_one_worker_before_attempt_start(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    transactions = SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor)
    with transactions.begin() as transaction:
        first = transaction.prepare(seeded.node_run_id, "issue-89-owner")
        assert first.committed_result is None

    with pytest.raises(NodeExecutionError) as caught:
        with transactions.begin() as transaction:
            transaction.prepare(seeded.node_run_id, "issue-89-owner")

    assert caught.value.code == "NODE_EXECUTION_IN_FLIGHT"


async def test_video_shot_candidates_cannot_satisfy_selected_clips_context(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    with factory() as session, session.begin():
        run = session.get(WorkflowRun, seeded.workflow_run_id)
        definition = session.scalar(select(ContentDefinitionVersion))
        assert run is not None and definition is not None
        lesson = LessonUnit(
            id=new_uuid7(),
            organization_id=seeded.actor.organization_id,
            project_id=seeded.project_id,
            lesson_key="LESSON-SELECTED-CLIPS",
            position=1,
            title="Selected clips gate",
            scope_summary="Selected clips must be explicit",
            objective_summary="Reject candidate-only context",
            estimated_minutes=40,
            source_division_version_id=seeded.upstream_version_id,
            status="active",
            created_by=seeded.actor.principal_id,
            updated_by=seeded.actor.principal_id,
        )
        session.add(lesson)
        session.flush()
        branch = BranchRun(
            id=new_uuid7(),
            workflow_run_id=run.id,
            lesson_unit_id=lesson.id,
            branch_key="video",
            status="active",
            created_by=seeded.actor.principal_id,
            updated_by=seeded.actor.principal_id,
        )
        session.add(branch)
        session.flush()
        node = NodeRun(
            id=new_uuid7(),
            organization_id=seeded.actor.organization_id,
            workflow_run_id=run.id,
            branch_run_id=branch.id,
            node_key="audio.plan.generate",
            run_no=1,
            status=NodeStatus.READY.value,
            trigger_type="manual",
            automation_policy_snapshot_json=run.automation_policy_snapshot_json,
            created_by=seeded.actor.principal_id,
            updated_by=seeded.actor.principal_id,
        )
        session.add(node)
        _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            definition.id,
            artifact_key="selected-clips-intro",
            artifact_type="intro_selection",
            branch_key="intro_options",
            lesson_unit_id=lesson.id,
        )
        _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            definition.id,
            artifact_key="selected-clips-master-script",
            artifact_type="video_master_script",
            branch_key="video",
            lesson_unit_id=lesson.id,
        )
        _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            definition.id,
            artifact_key="unselected-video-candidate",
            artifact_type="video_shot_generation",
            branch_key="video",
            lesson_unit_id=lesson.id,
        )

    provider = DeterministicNodeOutputProvider({})
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_AUDIO_PLAN: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodePromptPlanError) as caught:
        await service.execute(node.id, request_id="issue-89-selected-clips-fail-closed")

    assert caught.value.code == "CONTEXT_REQUIRED_MISSING"
    assert provider.calls == 0
    with factory() as session:
        assert _count(session, GenerationAttempt, "node_run_id", node.id) == 0
        assert _count(session, ArtifactVersion, "source_node_run_id", node.id) == 0
        assert _count(session, PromptSnapshot, "node_run_id", node.id) == 0
        assert _count(session, ContextSnapshot, "node_run_id", node.id) == 0


async def test_failed_attempt_can_retry_with_same_frozen_inputs(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    failed_provider = DeterministicFakeTextProvider(FakeScenario.RATE_LIMITED)
    failed_service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: failed_provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    with pytest.raises(NodeExecutionError) as caught:
        await failed_service.execute(seeded.node_run_id, request_id="issue-89-retry")
    assert caught.value.code == "PROVIDER_RATE_LIMITED"

    success_provider = DeterministicNodeOutputProvider(seeded.output)
    success_service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: success_provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    result = await success_service.execute(seeded.node_run_id, request_id="issue-89-retry")

    assert result.attempt_id is not None
    assert success_provider.calls == 1
    with factory() as session:
        attempts = list(
            session.scalars(
                select(GenerationAttempt)
                .where(GenerationAttempt.node_run_id == seeded.node_run_id)
                .order_by(GenerationAttempt.attempt_no)
            )
        )
        node = session.get(NodeRun, seeded.node_run_id)
        assert [attempt.attempt_no for attempt in attempts] == [1, 2]
        assert [attempt.status for attempt in attempts] == ["failed", "succeeded"]
        assert node is not None and node.status == NodeStatus.REVIEW_REQUIRED.value


async def test_cross_tenant_node_execution_is_rejected_before_provider(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    foreign = ActorContext(
        organization_id=UUID("01900000-0000-7000-8000-000000000099"),
        principal_id=UUID("01900000-0000-7000-8000-000000000199"),
        user_id=None,
        actor_type="system",
        organization_role="owner",
    )
    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, foreign),
        ModelGateway({ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider}),
    )

    with pytest.raises(WorkflowExecutionPortError) as caught:
        await service.execute(seeded.node_run_id, request_id="issue-89-foreign")
    assert caught.value.code == "NODE_EXECUTION_NOT_FOUND"
    assert provider.calls == 0


async def test_stale_propagation_marks_generated_node_and_artifact(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    provider = DeterministicNodeOutputProvider(seeded.output)
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    result = await service.execute(seeded.node_run_id, request_id="issue-89-stale")

    with factory() as session, session.begin():
        source = session.get(ArtifactVersion, seeded.upstream_version_id)
        assert source is not None
        replacement = ArtifactVersion(
            id=new_uuid7(),
            organization_id=seeded.actor.organization_id,
            artifact_id=source.artifact_id,
            version_no=2,
            content_json={"replacement": True},
            content_hash="b" * 64,
            render_summary_json={},
            source_kind="manual",
            source_node_run_id=None,
            context_snapshot_id=None,
            prompt_snapshot_id=None,
            validation_report_json={"valid": True},
            created_by=seeded.actor.principal_id,
        )
        session.add(replacement)
        session.flush()
        source_artifact = session.get(Artifact, source.artifact_id)
        assert source_artifact is not None
        source_artifact.current_approved_version_id = replacement.id
        ArtifactRelationService(session, seeded.actor).propagate_stale(
            seeded.upstream_version_id,
            replacement.id,
        )

    with factory() as session:
        target = session.get(ArtifactVersion, result.artifact_version_id)
        assert target is not None
        artifact = session.get(Artifact, target.artifact_id)
        node = session.get(NodeRun, seeded.node_run_id)
        assert artifact is not None and artifact.status == "stale"
        assert node is not None and node.status == NodeStatus.STALE.value


async def test_creation_package_publish_is_bound_to_fixed_source_and_target(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = _seed_runtime(factory)
    with factory() as session, session.begin():
        definition_row = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.definition_key == "ppt.body_asset_prompts.generate.output"
            )
        )
        run = session.get(WorkflowRun, seeded.workflow_run_id)
        assert definition_row is not None and run is not None
        lesson = LessonUnit(
            id=new_uuid7(),
            organization_id=seeded.actor.organization_id,
            project_id=seeded.project_id,
            lesson_key="LESSON-001",
            position=1,
            title="Numbers 1 to 5",
            scope_summary="Approved scope",
            objective_summary="Recognize numbers 1 to 5",
            estimated_minutes=40,
            source_division_version_id=seeded.upstream_version_id,
            status="active",
            created_by=seeded.actor.principal_id,
            updated_by=seeded.actor.principal_id,
        )
        session.add(lesson)
        session.flush()
        branch = BranchRun(
            id=new_uuid7(),
            workflow_run_id=run.id,
            lesson_unit_id=lesson.id,
            branch_key="ppt",
            status="active",
            created_by=seeded.actor.principal_id,
            updated_by=seeded.actor.principal_id,
        )
        session.add(branch)
        session.flush()
        node = NodeRun(
            id=new_uuid7(),
            organization_id=seeded.actor.organization_id,
            workflow_run_id=run.id,
            branch_run_id=branch.id,
            node_key="ppt.body_asset_prompts.generate",
            run_no=1,
            status=NodeStatus.READY.value,
            trigger_type="manual",
            automation_policy_snapshot_json=run.automation_policy_snapshot_json,
            created_by=seeded.actor.principal_id,
            updated_by=seeded.actor.principal_id,
        )
        session.add(node)
        session.flush()
        _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            definition_row.id,
            artifact_key="ppt-page-specs:LESSON-001",
            artifact_type="ppt_page_specs",
            branch_key="ppt",
            lesson_unit_id=lesson.id,
        )
        _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            definition_row.id,
            artifact_key="lesson-plan:LESSON-001",
            artifact_type="lesson_plan",
            branch_key="lesson_plan",
            lesson_unit_id=lesson.id,
        )
        _seed_approved_artifact(
            session,
            seeded.actor,
            seeded.project_id,
            definition_row.id,
            artifact_key="ppt-style:LESSON-001",
            artifact_type="ppt_style",
            branch_key="ppt",
            lesson_unit_id=lesson.id,
        )
        output = deepcopy(
            build_golden_branch_source_outputs(
                json.loads(GOLDEN_CASE_PATH.read_text(encoding="utf-8"))
            )["ppt.body_asset_prompts.generate"]
        )
        for item in output["body_asset_items"]:
            item["body_target_slot"] = item["body_target_slot"].lower()
        slots = tuple(item["body_target_slot"] for item in output["body_asset_items"])
        for slot_key in slots:
            session.add(
                ProjectAssetSlot(
                    id=new_uuid7(),
                    organization_id=seeded.actor.organization_id,
                    project_id=seeded.project_id,
                    lesson_unit_id=lesson.id,
                    slot_key=slot_key,
                    asset_type="image",
                    cardinality="one",
                    required=True,
                    status="empty",
                    target_contract_json={},
                    created_by=seeded.actor.principal_id,
                    updated_by=seeded.actor.principal_id,
                )
            )
        session.flush()

    provider = DeterministicNodeOutputProvider(output)
    service = NodeExecutionService(
        SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor),
        ModelGateway(
            {ModelCapability.TEXT_STRUCTURED_IMAGE_PROMPT: provider},
            audit_sink=SqlAlchemyAttemptAuditSink(factory),
        ),
    )
    first = await service.execute(node.id, request_id="issue-89-package-source")
    replay = await service.execute(node.id, request_id="issue-89-package-source")
    assert replay == first
    assert provider.calls == 1

    with factory() as session:
        package = session.get(CreationPackage, first.creation_package_id)
        items = list(
            session.scalars(
                select(CreationPackageItem)
                .where(CreationPackageItem.creation_package_id == first.creation_package_id)
                .order_by(CreationPackageItem.position)
            )
        )
        assert package is not None
        context = session.scalar(
            select(ContextSnapshot).where(ContextSnapshot.node_run_id == node.id)
        )
        prompt = session.scalar(select(PromptSnapshot).where(PromptSnapshot.node_run_id == node.id))
        assert context is not None and prompt is not None
        assert package.source_artifact_version_id == first.artifact_version_id
        assert package.source_node_run_id == node.id
        assert package.source_workflow_run_id == seeded.workflow_run_id
        assert package.lesson_unit_id == lesson.id
        assert package.context_snapshot_id == context.id
        assert package.source_prompt_snapshot_id == prompt.id
        assert package.target_rules_json == {
            "replace_modes": ["reject_if_occupied", "replace_active"],
            "allow_download": True,
        }
        assert [item.target_slot_key for item in items] == list(slots)
        assert all(item.reference_assets_json == [] for item in items)
        assert (
            session.scalar(
                select(func.count())
                .select_from(CreationPackage)
                .where(CreationPackage.source_node_run_id == node.id)
            )
            == 1
        )


def _seed_runtime(factory: sessionmaker[Session]) -> RuntimeSeed:
    case = json.loads(GOLDEN_CASE_PATH.read_text(encoding="utf-8"))
    output = build_golden_branch_source_outputs(case)["lesson.division.generate"]
    source = load_builtin_courseware_release(ROOT)
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        published = ContentReleasePublisher(session).publish(
            source,
            published_by=actor.principal_id,
        )
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Issue 89 golden runtime", knowledge_point="1-5")
        )
        run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
        definition = session.scalar(
            select(ContentDefinitionVersion).where(
                ContentDefinitionVersion.content_package_version_id
                == published.content_package_version_id,
                ContentDefinitionVersion.definition_key == "lesson.division.generate.output",
            )
        )
        assert definition is not None
        _seed_material_context(session, actor, project.id, case)
        upstream = _seed_approved_scope(
            session,
            actor,
            project.id,
            definition.id,
            output,
        )
        node = WorkflowRuntimeService(session, actor).create_project_node_run(
            run.id,
            node_key="lesson.division.generate",
            status=NodeStatus.READY,
        )
    return RuntimeSeed(
        actor=actor,
        project_id=project.id,
        workflow_run_id=run.id,
        node_run_id=node.id,
        upstream_version_id=upstream.id,
        output=output,
    )


async def _checkpoint_recovery_fact(
    factory: sessionmaker[Session],
    seeded: RuntimeSeed,
    request_id: str,
) -> tuple[SqlAlchemyNodeExecutionTransactionFactory, PreparedNodeExecution]:
    transactions = SqlAlchemyNodeExecutionTransactionFactory(factory, seeded.actor)
    with transactions.begin() as transaction:
        prepared = transaction.prepare(seeded.node_run_id, request_id)
    gateway = ModelGateway(
        {
            ModelCapability.TEXT_STRUCTURED_ZH_PRIMARY_MATH: DeterministicNodeOutputProvider(
                seeded.output
            )
        },
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    pending = await gateway.generate_text_pending(
        prepared.request,
        audit_context=prepared.audit_context,
    )
    output = validate_structured_output(pending.result.text, prepared.output_schema)
    with transactions.begin() as transaction:
        transaction.checkpoint(prepared, output, pending)
    return transactions, prepared


def _seed_material_context(
    session: Session,
    actor: ActorContext,
    project_id: UUID,
    case: dict[str, object],
) -> None:
    asset = FileAsset(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        asset_key=f"issue-89-material:{project_id}",
        asset_kind="source_material",
        current_version_id=None,
        status="active",
        retention_class="project",
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(asset)
    session.flush()
    version = FileAssetVersion(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        file_asset_id=asset.id,
        version_no=1,
        storage_bucket="test-only",
        storage_key=f"issue-89/{project_id}/material.pdf",
        mime_type="application/pdf",
        byte_size=1,
        sha256="a" * 64,
        etag="issue-89",
        width=None,
        height=None,
        duration_ms=None,
        page_count=1,
        scan_status="clean",
        metadata_json={},
        derived_from_version_id=None,
        created_at=utc_now(),
        created_by=actor.principal_id,
    )
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    material = SourceMaterial(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project_id,
        material_kind="textbook",
        file_asset_id=asset.id,
        original_filename="issue-89-material.pdf",
        mime_type="application/pdf",
        upload_status="confirmed",
        confirmed_at=utc_now(),
        confirmed_by=actor.principal_id,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(material)
    session.flush()
    content = {
        "source": case["source"],
        "material_evidence": case["material_evidence"],
    }
    session.add(
        MaterialParseVersion(
            id=new_uuid7(),
            organization_id=actor.organization_id,
            source_material_id=material.id,
            file_asset_version_id=version.id,
            generation_job_id=None,
            version_no=1,
            status="succeeded",
            parser_name="issue-89-fake",
            parser_version="1",
            content_json=content,
            page_count=1,
            text_checksum=canonical_content_hash(content),
            validation_report_json={"valid": True},
            error_code=None,
            created_at=utc_now(),
            started_at=utc_now(),
            completed_at=utc_now(),
            created_by=actor.principal_id,
            updated_by=actor.principal_id,
        )
    )
    session.flush()


def _seed_approved_scope(
    session: Session,
    actor: ActorContext,
    project_id: UUID,
    definition_id: UUID,
    content: dict[str, object],
) -> ArtifactVersion:
    return _seed_approved_artifact(
        session,
        actor,
        project_id,
        definition_id,
        artifact_key="material-scope",
        artifact_type="material_scope",
        branch_key="project",
        lesson_unit_id=None,
        content=content,
    )


def _seed_approved_artifact(
    session: Session,
    actor: ActorContext,
    project_id: UUID,
    definition_id: UUID,
    *,
    artifact_key: str,
    artifact_type: str,
    branch_key: str,
    lesson_unit_id: UUID | None,
    content: dict[str, object] | None = None,
) -> ArtifactVersion:
    artifact = Artifact(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        project_id=project_id,
        lesson_unit_id=lesson_unit_id,
        branch_key=branch_key,
        artifact_key=artifact_key,
        artifact_type=artifact_type,
        content_definition_version_id=definition_id,
        status="approved",
        stale_reason_json=None,
        created_by=actor.principal_id,
        updated_by=actor.principal_id,
    )
    session.add(artifact)
    session.flush()
    version = ArtifactVersion(
        id=new_uuid7(),
        organization_id=actor.organization_id,
        artifact_id=artifact.id,
        version_no=1,
        content_json=content or {"artifact_type": artifact_type},
        content_hash=canonical_content_hash(content or {"artifact_type": artifact_type}),
        render_summary_json={},
        source_kind="manual",
        source_node_run_id=None,
        context_snapshot_id=None,
        prompt_snapshot_id=None,
        validation_report_json={"valid": True},
        created_by=actor.principal_id,
    )
    session.add(version)
    session.flush()
    artifact.current_approved_version_id = version.id
    session.flush()
    return version


def _count(session: Session, model: type[object], column: str, value: UUID) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(model).where(getattr(model, column) == value)
        )
        or 0
    )
