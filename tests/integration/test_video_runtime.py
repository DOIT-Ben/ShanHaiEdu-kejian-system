from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.artifacts.models import Artifact
from apps.api.assets.models import FileAsset, FileAssetVersion
from apps.api.assets.project_models import AssetBinding, ProjectAssetSlot
from apps.api.creation.models import Adoption, CreationBatch, CreationItem, GenerationResult
from apps.api.creation.schemas import (
    AdoptGenerationResultRequest,
    ProjectSourceSaveRequest,
)
from apps.api.creation.service import CreationService
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.identity.context import ActorContext
from apps.api.identity.models import Organization
from apps.api.intro_selections.service import IntroSelectionService
from apps.api.model_gateway.contracts import (
    GeneratedFileFact,
    ModelCapability,
    ModelUsage,
    RouteDecision,
    VideoGatewayResult,
    VideoModelRequest,
    VideoOperationStatus,
    VideoPollRequest,
)
from apps.api.video_runtime.contracts import ValidatedVideoFile, VideoRuntimeError
from apps.api.video_runtime.service import VideoRuntimeService
from apps.api.video_runtime.sqlalchemy import SqlAlchemyVideoRuntimeTransactionFactory
from apps.api.workflows.models import BranchRun, NodeRun, WorkflowRun
from apps.api.workflows.service import WorkflowRuntimeService
from tests.integration.intro_selection_support import prepare_approved_option_set
from tests.integration.test_project_asset_bindings import (
    seed_file_version,  # pyright: ignore[reportUnknownVariableType]
)
from workflow.node_state import NodeStatus


@dataclass(frozen=True, slots=True)
class VideoRuntimeSeed:
    actor: ActorContext
    project_id: UUID
    lesson_unit_id: UUID
    node_run_id: UUID
    intro_artifact_id: UUID
    keyframe_version_id: UUID


class FakeVideoGateway:
    def __init__(
        self,
        submit_result: VideoGatewayResult | Exception,
        *,
        poll_result: VideoGatewayResult | Exception | None = None,
    ) -> None:
        self.submit_result = submit_result
        self.poll_result = poll_result
        self.calls: list[tuple[str, VideoModelRequest | VideoPollRequest]] = []

    async def submit_video(
        self,
        request: VideoModelRequest,
        **_kwargs: object,
    ) -> VideoGatewayResult:
        self.calls.append(("submit", request))
        if isinstance(self.submit_result, Exception):
            raise self.submit_result
        return self.submit_result

    async def poll_video(
        self,
        request: VideoPollRequest,
        **_kwargs: object,
    ) -> VideoGatewayResult:
        self.calls.append(("poll", request))
        if self.poll_result is None:
            raise AssertionError("unexpected poll")
        if isinstance(self.poll_result, Exception):
            raise self.poll_result
        return self.poll_result


class FakeVideoValidator:
    def __init__(self, validated: ValidatedVideoFile) -> None:
        self.validated = validated
        self.calls: list[GeneratedFileFact] = []

    def validate(self, file: GeneratedFileFact) -> ValidatedVideoFile:
        self.calls.append(file)
        return self.validated


async def test_completed_video_is_candidate_only_until_teacher_adopts_and_saves(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = await _seed_video_runtime(factory)
    file_fact, validated = _video_file()
    gateway = FakeVideoGateway(_gateway_result(VideoOperationStatus.SUCCEEDED, file_fact))
    service = VideoRuntimeService(
        SqlAlchemyVideoRuntimeTransactionFactory(factory, seeded.actor),
        gateway,
        FakeVideoValidator(validated),
    )

    completed = await service.start(
        seeded.node_run_id,
        keyframe_file_version_id=seeded.keyframe_version_id,
        request_id="issue-205-video-start",
    )

    assert completed.status == "completed"
    assert completed.generation_result_id is not None
    assert completed.file_asset_version_id is not None
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        result = session.get(GenerationResult, completed.generation_result_id)
        item = session.get(CreationItem, result.creation_item_id if result else None)
        slot = session.scalar(
            select(ProjectAssetSlot).where(ProjectAssetSlot.project_id == seeded.project_id)
        )
        assert node is not None and node.status == NodeStatus.REVIEW_REQUIRED.value
        assert result is not None and result.status == "available"
        assert item is not None and item.status == "review_required"
        assert slot is not None
        assert slot.asset_type == "video"
        assert slot.cardinality == "one"
        assert slot.target_contract_json["allowed_mime_types"] == ["video/mp4"]
        assert session.scalar(select(func.count()).select_from(Adoption)) == 0
        assert session.scalar(select(func.count()).select_from(AssetBinding)) == 0

    with factory() as session:
        creation = CreationService(session, seeded.actor, idempotency_ttl_seconds=3600)
        with session.begin():
            adoption = creation.adopt_result(
                completed.generation_result_id,
                AdoptGenerationResultRequest(reason="Use this classroom hook."),
                idempotency_key="issue-205-adopt",
                request_id="issue-205-adopt",
            )
        assert session.scalar(select(func.count()).select_from(AssetBinding)) == 0
        session.rollback()
        with session.begin():
            saved = creation.save_adoption(
                adoption.id,
                ProjectSourceSaveRequest(
                    source_kind="project",
                    replace_mode="reject_if_occupied",
                ),
                idempotency_key="issue-205-save",
                request_id="issue-205-save",
            )
        binding = session.get(AssetBinding, saved.binding_id)
        assert binding is not None
        assert binding.source_generation_result_id == completed.generation_result_id
        assert binding.file_asset_version_id == completed.file_asset_version_id


async def test_pending_video_can_be_polled_to_one_candidate(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = await _seed_video_runtime(factory)
    file_fact, validated = _video_file()
    gateway = FakeVideoGateway(
        _gateway_result(VideoOperationStatus.SUBMITTED),
        poll_result=_gateway_result(VideoOperationStatus.SUCCEEDED, file_fact),
    )
    service = VideoRuntimeService(
        SqlAlchemyVideoRuntimeTransactionFactory(factory, seeded.actor),
        gateway,
        FakeVideoValidator(validated),
    )

    submitted = await service.start(
        seeded.node_run_id,
        keyframe_file_version_id=seeded.keyframe_version_id,
        request_id="issue-205-submit",
    )
    completed = await service.poll(seeded.node_run_id, request_id="issue-205-poll")

    assert submitted.status == "submitted"
    assert completed.status == "completed"
    assert [kind for kind, _ in gateway.calls] == ["submit", "poll"]
    poll_request = gateway.calls[1][1]
    assert isinstance(poll_request, VideoPollRequest)
    assert poll_request.provider_task_id == "provider-task-205"
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(GenerationResult)
                .where(GenerationResult.creation_item_id == session.scalar(select(CreationItem.id)))
            )
            == 1
        )


@pytest.mark.parametrize("invalid_state", ["scan_pending", "asset_rejected"])
async def test_non_formal_keyframe_is_rejected_before_provider(
    migrated_database_url: str,
    invalid_state: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = await _seed_video_runtime(factory)
    with factory() as session, session.begin():
        version = session.get(FileAssetVersion, seeded.keyframe_version_id)
        assert version is not None
        asset = session.get(FileAsset, version.file_asset_id)
        assert asset is not None
        if invalid_state == "scan_pending":
            version.scan_status = "pending"
        else:
            asset.status = "rejected"
    gateway = FakeVideoGateway(_gateway_result(VideoOperationStatus.SUBMITTED))
    service = VideoRuntimeService(
        SqlAlchemyVideoRuntimeTransactionFactory(factory, seeded.actor),
        gateway,
        FakeVideoValidator(_video_file()[1]),
    )

    with pytest.raises(VideoRuntimeError) as caught:
        await service.start(
            seeded.node_run_id,
            keyframe_file_version_id=seeded.keyframe_version_id,
            request_id=f"issue-205-{invalid_state}",
        )

    assert caught.value.code == "VIDEO_RUNTIME_KEYFRAME_INVALID"
    assert gateway.calls == []


async def test_cross_tenant_keyframe_is_rejected_before_provider(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = await _seed_video_runtime(factory)
    with factory() as session, session.begin():
        outsider_organization_id = uuid4()
        session.add(
            Organization(
                id=outsider_organization_id,
                slug=f"issue-205-{outsider_organization_id.hex[:12]}",
                name="Issue 205 outsider",
                status="active",
                created_at=utc_now(),
            )
        )
        session.flush()
        outsider_version = seed_file_version(
            session,
            seeded.actor,
            organization_id=outsider_organization_id,
        )
    gateway = FakeVideoGateway(_gateway_result(VideoOperationStatus.SUBMITTED))
    service = VideoRuntimeService(
        SqlAlchemyVideoRuntimeTransactionFactory(factory, seeded.actor),
        gateway,
        FakeVideoValidator(_video_file()[1]),
    )

    with pytest.raises(VideoRuntimeError) as caught:
        await service.start(
            seeded.node_run_id,
            keyframe_file_version_id=outsider_version.id,
            request_id="issue-205-cross-tenant",
        )

    assert caught.value.code == "VIDEO_RUNTIME_KEYFRAME_INVALID"
    assert gateway.calls == []


async def test_stale_intro_selection_is_rejected_before_provider(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = await _seed_video_runtime(factory)
    with factory() as session, session.begin():
        artifact = session.get(Artifact, seeded.intro_artifact_id)
        assert artifact is not None
        artifact.status = "stale"
        artifact.stale_reason_json = {"reason_code": "UPSTREAM_CHANGED"}
    gateway = FakeVideoGateway(_gateway_result(VideoOperationStatus.SUBMITTED))
    service = VideoRuntimeService(
        SqlAlchemyVideoRuntimeTransactionFactory(factory, seeded.actor),
        gateway,
        FakeVideoValidator(_video_file()[1]),
    )

    with pytest.raises(VideoRuntimeError) as caught:
        await service.start(
            seeded.node_run_id,
            keyframe_file_version_id=seeded.keyframe_version_id,
            request_id="issue-205-stale-intro",
        )

    assert caught.value.code == "VIDEO_RUNTIME_INTRO_SELECTION_INVALID"
    assert gateway.calls == []


async def test_provider_failure_terminalizes_without_candidate(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = await _seed_video_runtime(factory)
    gateway = FakeVideoGateway(_gateway_result(VideoOperationStatus.FAILED))
    service = VideoRuntimeService(
        SqlAlchemyVideoRuntimeTransactionFactory(factory, seeded.actor),
        gateway,
        FakeVideoValidator(_video_file()[1]),
    )

    with pytest.raises(VideoRuntimeError) as caught:
        await service.start(
            seeded.node_run_id,
            keyframe_file_version_id=seeded.keyframe_version_id,
            request_id="issue-205-provider-failed",
        )

    assert caught.value.code == "VIDEO_RUNTIME_PROVIDER_FAILED"
    with factory() as session:
        node = session.get(NodeRun, seeded.node_run_id)
        item = session.scalar(select(CreationItem))
        batch = session.scalar(select(CreationBatch))
        assert node is not None and node.status == NodeStatus.FAILED.value
        assert item is not None and item.status == "failed"
        assert batch is not None and batch.status == "partially_completed"
        assert session.scalar(select(func.count()).select_from(GenerationResult)) == 0


async def test_completion_fault_rolls_back_file_and_candidate_atomically(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    seeded = await _seed_video_runtime(factory)
    file_fact, validated = _video_file()

    def inject(stage: str) -> None:
        if stage == "after_generation_result":
            raise RuntimeError("simulated completion fault")

    service = VideoRuntimeService(
        SqlAlchemyVideoRuntimeTransactionFactory(
            factory,
            seeded.actor,
            fault_injector=inject,
        ),
        FakeVideoGateway(_gateway_result(VideoOperationStatus.SUCCEEDED, file_fact)),
        FakeVideoValidator(validated),
    )

    with pytest.raises(VideoRuntimeError) as caught:
        await service.start(
            seeded.node_run_id,
            keyframe_file_version_id=seeded.keyframe_version_id,
            request_id="issue-205-completion-fault",
        )

    assert caught.value.code == "VIDEO_RUNTIME_COMMIT_FAILED"
    with factory() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(FileAsset).where(FileAsset.asset_kind == "video")
            )
            == 0
        )
        assert session.scalar(select(func.count()).select_from(GenerationResult)) == 0


async def _seed_video_runtime(factory: sessionmaker[Session]) -> VideoRuntimeSeed:
    prepared = await prepare_approved_option_set(factory)
    with factory() as session, session.begin():
        IntroSelectionService(session, prepared.actor).select_teacher(
            project_id=prepared.project_id,
            lesson_unit_id=prepared.lesson_unit_id,
            artifact_version_id=prepared.version_id,
            option_key=prepared.option_keys[0],
            reason="Use the science hook for the video MVP.",
            idempotency_key=f"issue-205-select-{uuid4()}",
            ttl_seconds=3600,
        )
    with factory() as session, session.begin():
        run = session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.project_id == prepared.project_id,
                WorkflowRun.status == "active",
            )
        )
        assert run is not None
        branch = session.scalar(
            select(BranchRun).where(
                BranchRun.workflow_run_id == run.id,
                BranchRun.lesson_unit_id == prepared.lesson_unit_id,
                BranchRun.branch_key == "video",
            )
        )
        assert branch is not None
        branch.status = "active"
        branch.started_at = branch.started_at or utc_now()
        session.flush()
        node = WorkflowRuntimeService(session, prepared.actor).create_branch_node_run(
            run.id,
            branch.id,
            node_key="video.shots.generate",
            status=NodeStatus.READY,
        )
        keyframe = seed_file_version(session, prepared.actor)
    return VideoRuntimeSeed(
        actor=prepared.actor,
        project_id=prepared.project_id,
        lesson_unit_id=prepared.lesson_unit_id,
        node_run_id=node.id,
        intro_artifact_id=prepared.artifact_id,
        keyframe_version_id=keyframe.id,
    )


def _video_file() -> tuple[GeneratedFileFact, ValidatedVideoFile]:
    storage_key = f"video-runtime/{uuid4()}/candidate.mp4"
    fact = GeneratedFileFact(
        storage_key=storage_key,
        sha256="b" * 64,
        size_bytes=4096,
        mime_type="video/mp4",
        width=1280,
        height=720,
        duration_seconds=6,
    )
    return fact, ValidatedVideoFile(
        storage_bucket="shanhaiedu",
        storage_key=storage_key,
        etag=f"etag-{uuid4()}",
        mime_type="video/mp4",
        size_bytes=4096,
        sha256="b" * 64,
        width=1280,
        height=720,
        duration_ms=6000,
    )


def _gateway_result(
    status: VideoOperationStatus,
    file: GeneratedFileFact | None = None,
) -> VideoGatewayResult:
    return VideoGatewayResult(
        request_id=f"gateway-{uuid4()}",
        status=status,
        route=RouteDecision(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            provider="fake-video",
            model="fake-video-v1",
            reason="configured_route",
        ),
        provider_request_id="provider-request-205",
        provider_task_id="provider-task-205",
        actual_model="fake-video-v1",
        files=[file] if file is not None else [],
        usage=ModelUsage(output_units={"video_seconds": 6}, cost=Decimal("0")),
        latency_ms=1,
    )
