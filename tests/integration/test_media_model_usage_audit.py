from __future__ import annotations

import pytest
from sqlalchemy import select

from apps.api.database import build_engine, build_session_factory
from apps.api.model_gateway.audit import SqlAlchemyAttemptAuditSink
from apps.api.model_gateway.audit_models import GenerationAttempt, UsageRecord
from apps.api.model_gateway.contracts import (
    GatewayErrorCode,
    ImageModelRequest,
    ModelAuditContext,
    ModelCapability,
    ModelGatewayError,
    VideoModelRequest,
    VideoPollRequest,
)
from apps.api.model_gateway.fake import (
    DeterministicFakeImageProvider,
    DeterministicFakeVideoProvider,
    FakeVideoScenario,
)
from apps.api.model_gateway.gateway import ModelGateway
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.identity import seed_test_actor
from workflow.node_state import NodeStatus


async def test_media_attempts_persist_task_identity_and_provider_neutral_usage(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Media audit", knowledge_point="One half")
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
    image_gateway = ModelGateway(
        {},
        image_routes={
            ModelCapability.IMAGE_GENERATE_EDUCATION_16X9: DeterministicFakeImageProvider()
        },
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    video_provider = DeterministicFakeVideoProvider()
    video_gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: video_provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )

    await image_gateway.generate_image(
        ImageModelRequest(
            capability=ModelCapability.IMAGE_GENERATE_EDUCATION_16X9,
            request_id="req-audit-image",
            prompt="PRIVATE_IMAGE_PROMPT",
            width=1280,
            height=720,
        ),
        audit_context=audit_context,
    )
    submitted = await video_gateway.submit_video(
        VideoModelRequest(
            capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
            request_id="req-audit-video-submit",
            prompt="PRIVATE_VIDEO_PROMPT",
            duration_seconds=8,
            references=[],
        ),
        audit_context=audit_context,
    )
    assert submitted.provider_task_id is not None

    with factory() as session:
        submit_attempt = session.scalar(
            select(GenerationAttempt).where(
                GenerationAttempt.request_id == "req-audit-video-submit"
            )
        )
    assert submit_attempt is not None
    assert submit_attempt.provider_task_id == submitted.provider_task_id

    for index in (1, 2):
        await video_gateway.poll_video(
            VideoPollRequest(
                capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
                request_id=f"req-audit-video-poll-{index}",
                provider_task_id=submitted.provider_task_id,
            ),
            audit_context=audit_context,
        )

    unknown_provider = DeterministicFakeVideoProvider(FakeVideoScenario.SUBMISSION_UNKNOWN)
    unknown_gateway = ModelGateway(
        {},
        video_routes={ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S: unknown_provider},
        audit_sink=SqlAlchemyAttemptAuditSink(factory),
    )
    with pytest.raises(ModelGatewayError) as unknown:
        await unknown_gateway.submit_video(
            VideoModelRequest(
                capability=ModelCapability.VIDEO_IMAGE_TO_VIDEO_6S_30S,
                request_id="req-audit-video-unknown",
                prompt="PRIVATE_UNKNOWN_SUBMISSION_PROMPT",
                duration_seconds=8,
                references=[],
            ),
            audit_context=audit_context,
        )
    assert unknown.value.code == GatewayErrorCode.SUBMISSION_UNKNOWN
    assert unknown.value.retryable is False
    assert unknown_provider.submit_calls == 1

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

    assert [attempt.attempt_no for attempt in attempts] == [1, 2, 3, 4, 5]
    assert [attempt.provider_task_id for attempt in attempts] == [
        None,
        submitted.provider_task_id,
        submitted.provider_task_id,
        submitted.provider_task_id,
        None,
    ]
    assert usage[0].input_units_json == {"prompt_tokens": 0}
    assert usage[0].output_units_json == {
        "completion_tokens": 0,
        "images": 1,
        "total_tokens": 0,
    }
    assert usage[-2].output_units_json == {
        "completion_tokens": 0,
        "total_tokens": 0,
        "video_seconds": 8,
    }
    assert attempts[-1].status == "failed"
    assert attempts[-1].error_code == "MODEL_SUBMISSION_UNKNOWN"
    assert attempts[-1].error_details_json == {
        "retryable": False,
        "retry_after_seconds": None,
    }
    persisted = repr(
        [
            (attempt.request_hash, attempt.error_details_json, record.output_units_json)
            for attempt, record in zip(attempts, usage, strict=True)
        ]
    )
    assert "PRIVATE_IMAGE_PROMPT" not in persisted
    assert "PRIVATE_VIDEO_PROMPT" not in persisted
    assert "PRIVATE_UNKNOWN_SUBMISSION_PROMPT" not in persisted
