from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from apps.api.artifacts.models import Approval, Artifact
from apps.api.artifacts.repository import ArtifactRepository
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry, OutboxEvent
from tests.fakes.content_runtime import ensure_test_authoring_definition
from tests.fakes.identity import seed_test_actor


def test_approval_pointer_event_and_outbox_commit_or_rollback_together(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
            definition_id = ensure_test_authoring_definition(session, project.id)
            service = ArtifactService(session, actor)
            artifact = service.create(
                project.id,
                artifact_key="lesson-plan:lesson-01",
                artifact_type="lesson_plan",
                branch_key="lesson_plan",
                content_definition_version_id=definition_id,
                draft_branch="main",
                initial_content={"title": "Review me"},
                request_id="req-create",
            )
            draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
            assert draft is not None
            version = service.submit(
                artifact.id,
                "main",
                expected_lock_version=draft.lock_version,
                source_kind="manual",
                request_id="req-submit",
            )

        baseline_approvals = int(session.scalar(select(func.count()).select_from(Approval)) or 0)
        baseline_events = int(
            session.scalar(select(func.count()).select_from(EventStreamEntry)) or 0
        )
        baseline_outbox = int(session.scalar(select(func.count()).select_from(OutboxEvent)) or 0)
        session.rollback()

        try:
            with session.begin():
                ArtifactService(session, actor).review(
                    version.id,
                    action="approve",
                    comment="Looks good",
                    request_id="req-rollback",
                )
                raise RuntimeError("rollback")
        except RuntimeError:
            pass

        session.expire_all()
        rolled_back = session.get(Artifact, artifact.id)
        assert rolled_back is not None and rolled_back.current_approved_version_id is None
        assert session.scalar(select(func.count()).select_from(Approval)) == baseline_approvals
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == baseline_events
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == baseline_outbox
        session.rollback()

        with session.begin():
            approved = ArtifactService(session, actor).review(
                version.id,
                action="approve",
                comment="Looks good",
                request_id="req-approve",
            )
        with session.begin():
            replay = ArtifactService(session, actor).review(
                version.id,
                action="approve",
                comment="Duplicate",
                request_id="req-approve-again",
            )

        session.refresh(artifact)
        assert replay.id == approved.id
        assert artifact.current_approved_version_id == version.id
        assert artifact.status == "approved"
        assert session.scalar(select(func.count()).select_from(Approval)) == baseline_approvals + 1
        assert (
            session.scalar(select(func.count()).select_from(EventStreamEntry))
            == baseline_events + 1
        )
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == baseline_outbox + 1


def test_concurrent_double_approval_returns_one_deterministic_record(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        definition_id = ensure_test_authoring_definition(session, project.id)
        service = ArtifactService(session, actor)
        artifact = service.create(
            project.id,
            artifact_key="lesson-plan:concurrent",
            artifact_type="lesson_plan",
            branch_key="lesson_plan",
            content_definition_version_id=definition_id,
            draft_branch="main",
            initial_content={"title": "Concurrent review"},
            request_id="req-concurrent-create",
        )
        draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
        assert draft is not None
        version = service.submit(
            artifact.id,
            "main",
            expected_lock_version=draft.lock_version,
            source_kind="manual",
            request_id="req-concurrent-submit",
        )

    def approve(request_id: str):
        with factory() as worker_session, worker_session.begin():
            return (
                ArtifactService(worker_session, actor)
                .review(
                    version.id,
                    action="approve",
                    comment="Concurrent approval",
                    request_id=request_id,
                )
                .id
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        approval_ids = list(
            executor.map(approve, ("req-concurrent-approve-1", "req-concurrent-approve-2"))
        )

    assert approval_ids[0] == approval_ids[1]
    with factory() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Approval).where(Approval.action == "approve")
            )
            == 1
        )


def test_approved_version_is_no_longer_a_returnable_submission(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
            definition_id = ensure_test_authoring_definition(session, project.id)
            service = ArtifactService(session, actor)
            artifact = service.create(
                project.id,
                artifact_key="lesson-plan:terminal-approval",
                artifact_type="lesson_plan",
                branch_key="lesson_plan",
                content_definition_version_id=definition_id,
                draft_branch="main",
                initial_content={"title": "Approve once"},
                request_id="req-terminal-create",
            )
            draft = ArtifactRepository(session, actor).get_draft(artifact.id, "main")
            assert draft is not None
            version = service.submit(
                artifact.id,
                "main",
                expected_lock_version=draft.lock_version,
                source_kind="manual",
                request_id="req-terminal-submit",
            )
            service.review(
                version.id,
                action="approve",
                comment="Approved",
                request_id="req-terminal-approve",
            )

        session.refresh(artifact)
        assert artifact.current_submitted_version_id is None
        assert artifact.current_approved_version_id == version.id
        assert artifact.status == "approved"
        session.rollback()

        with pytest.raises(ApiError) as conflict:
            with session.begin():
                ArtifactService(session, actor).review(
                    version.id,
                    action="request_changes",
                    comment="Too late",
                    request_id="req-terminal-return",
                )
        assert conflict.value.code == "ARTIFACT_STATE_CONFLICT"

        session.refresh(artifact)
        assert artifact.current_approved_version_id == version.id
        assert artifact.status == "approved"
