from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select

from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.lessons.domain import ApprovedLessonDivision, ApprovedLessonItem
from apps.api.lessons.repository import LessonRepository
from apps.api.lessons.service import LessonService
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry
from apps.api.workflows.lesson_fanout import (
    LessonFanoutTarget,
    LessonWorkflowFanoutService,
)
from apps.api.workflows.models import BranchRun, NodeRun
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.identity import seed_test_actor

ROOT = Path(__file__).resolve().parents[2]
DIVISION_ID = UUID("10000000-0000-4000-8000-000000000125")


def test_published_topology_fanout_is_idempotent_and_respects_branch_configuration(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor, run_id, lesson_id = _seed_lesson(session)
            targets = _targets(session, actor, lesson_id)
            result = LessonWorkflowFanoutService(session, actor).synchronize(
                run_id,
                targets=targets,
                archived_lesson_unit_ids=(),
                request_id="req-fanout-first",
            )

        assert result.created_branch_count == 4
        assert result.created_node_count == 4
        branches = list(session.scalars(select(BranchRun).order_by(BranchRun.branch_key)))
        nodes = list(session.scalars(select(NodeRun).order_by(NodeRun.node_key)))
        assert [(item.branch_key, item.status) for item in branches] == [
            ("intro_options", "active"),
            ("lesson_plan", "active"),
            ("ppt", "disabled"),
            ("video", "disabled"),
        ]
        assert [(item.node_key, item.status) for item in nodes] == [
            ("intro.generate_options", "ready"),
            ("lesson_plan.generate", "ready"),
            ("ppt.content_analyze", "disabled"),
            ("video.master_script.generate", "disabled"),
        ]
        session.rollback()

        with session.begin():
            replay = LessonWorkflowFanoutService(session, actor).synchronize(
                run_id,
                targets=targets,
                archived_lesson_unit_ids=(),
                request_id="req-fanout-replay",
            )

        assert replay.created_branch_count == 0
        assert replay.created_node_count == 0
        assert session.scalar(select(func.count()).select_from(BranchRun)) == 4
        assert session.scalar(select(func.count()).select_from(NodeRun)) == 4
        assert (
            session.scalar(
                select(func.count())
                .select_from(EventStreamEntry)
                .where(EventStreamEntry.event_type == "workflow.lesson_branches.synchronized")
            )
            == 1
        )


def test_active_node_blocks_lesson_archive_until_cancellation_finishes(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor, run_id, lesson_id = _seed_lesson(session)
            LessonWorkflowFanoutService(session, actor).synchronize(
                run_id,
                targets=_targets(session, actor, lesson_id),
                archived_lesson_unit_ids=(),
                request_id="req-fanout",
            )
            node = session.scalar(select(NodeRun).where(NodeRun.node_key == "lesson_plan.generate"))
            assert node is not None
            node.status = "running"

        with pytest.raises(ApiError) as caught:
            with session.begin():
                LessonWorkflowFanoutService(session, actor).synchronize(
                    run_id,
                    targets=(),
                    archived_lesson_unit_ids=(lesson_id,),
                    request_id="req-archive-blocked",
                )
        assert caught.value.code == "LESSON_ARCHIVE_EXECUTION_ACTIVE"
        branch_status = session.scalar(
            select(BranchRun.status).where(BranchRun.branch_key == "lesson_plan")
        )
        assert branch_status == "active"
        session.rollback()

        with session.begin():
            node = session.get(NodeRun, node.id)
            assert node is not None
            node.status = "cancelled"
            LessonWorkflowFanoutService(session, actor).synchronize(
                run_id,
                targets=(),
                archived_lesson_unit_ids=(lesson_id,),
                request_id="req-archive-after-cancel",
            )

        assert set(session.scalars(select(BranchRun.status))) == {"cancelled"}
        assert session.get(NodeRun, node.id).status == "cancelled"


def _seed_lesson(session):
    actor = seed_test_actor(session)
    source = load_builtin_courseware_release(ROOT)
    ContentReleasePublisher(session).publish(source, published_by=actor.principal_id)
    project = ProjectRepository(session, actor).create(
        CreateProjectRequest(title="Lesson fanout", knowledge_point="One half")
    )
    run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
    lesson = LessonService(session, actor).synchronize_approved_division(
        project.id,
        ApprovedLessonDivision(
            version_id=DIVISION_ID,
            lessons=(
                ApprovedLessonItem(
                    lesson_key="LESSON-01",
                    position=1,
                    title="One half",
                    scope_summary="Approved scope",
                    objective_summary="Observable objective",
                    estimated_minutes=40,
                ),
            ),
        ),
        request_id="req-lesson-sync",
    )[0]
    return actor, run.id, lesson.id


def _targets(session, actor, lesson_id: UUID) -> tuple[LessonFanoutTarget, ...]:
    configs = LessonRepository(session, actor).list_branch_configs(lesson_id)
    return (
        LessonFanoutTarget(
            lesson_unit_id=lesson_id,
            branch_enabled={item.branch_key: item.enabled for item in configs},
        ),
    )
