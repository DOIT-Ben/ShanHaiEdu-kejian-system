from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import func, select

from apps.api.content_runtime.package_source import load_builtin_courseware_release
from apps.api.content_runtime.publication_service import ContentReleasePublisher
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.lessons.domain import (
    ApprovedLessonDivision,
    ApprovedLessonItem,
    BranchConfigurationChange,
    BranchKey,
)
from apps.api.lessons.models import LessonUnit
from apps.api.lessons.repository import LessonRepository
from apps.api.lessons.service import LessonService
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry
from apps.api.workflows.execution_port import (
    SqlAlchemyWorkflowExecutionPort,
    WorkflowExecutionPortError,
)
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
            lesson = session.get(LessonUnit, lesson_id)
            assert lesson is not None
            lesson.status = "archived"

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


@pytest.mark.parametrize(
    ("old_status", "retired_status"),
    [
        ("draft", "skipped"),
        ("failed", "skipped"),
        ("stale", "skipped"),
        ("paused", "cancelled"),
        ("partially_completed", "skipped"),
    ],
)
def test_branch_reenable_retires_old_entrypoint_and_creates_new_run(
    migrated_database_url: str,
    old_status: str,
    retired_status: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor, run_id, lesson_id = _seed_lesson(session)
        LessonWorkflowFanoutService(session, actor).synchronize(
            run_id,
            targets=_targets(session, actor, lesson_id),
            archived_lesson_unit_ids=(),
            request_id="req-branch-lifecycle",
        )
        old = session.scalar(select(NodeRun).where(NodeRun.node_key == "intro.generate_options"))
        lesson = LessonRepository(session, actor).get(lesson_id)
        assert old is not None and lesson is not None
        old.status = old_status
        LessonService(session, actor).update_branches(
            lesson_id,
            expected_version=lesson.lock_version,
            changes={
                BranchKey.INTRO_OPTIONS: BranchConfigurationChange(
                    enabled=False,
                    settings={},
                )
            },
            request_id="req-disable-before-reenable",
        )
        LessonService(session, actor).update_branches(
            lesson_id,
            expected_version=lesson.lock_version,
            changes={
                BranchKey.INTRO_OPTIONS: BranchConfigurationChange(
                    enabled=True,
                    settings={},
                )
            },
            request_id="req-reenable",
        )

    with factory() as session:
        nodes = list(
            session.scalars(
                select(NodeRun)
                .where(NodeRun.node_key == "intro.generate_options")
                .order_by(NodeRun.run_no)
            )
        )
        assert [(node.run_no, node.status) for node in nodes] == [
            (1, retired_status),
            (2, "ready"),
        ]


def test_fanout_rejects_cross_project_lesson_targets_before_writes(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor, run_id, _lesson_id = _seed_lesson(session)
            other_project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Other project", knowledge_point="Other")
            )
            other_lesson = LessonService(session, actor).synchronize_approved_division(
                other_project.id,
                ApprovedLessonDivision(
                    version_id=UUID("20000000-0000-4000-8000-000000000125"),
                    lessons=(
                        ApprovedLessonItem(
                            lesson_key="OTHER-LESSON",
                            position=1,
                            title="Other lesson",
                            scope_summary="Other scope",
                            objective_summary="Other objective",
                            estimated_minutes=40,
                        ),
                    ),
                ),
                request_id="req-other-lesson",
            )[0]
            other_target = _targets(session, actor, other_lesson.id)

        with pytest.raises(ApiError) as caught:
            with session.begin():
                LessonWorkflowFanoutService(session, actor).synchronize(
                    run_id,
                    targets=other_target,
                    archived_lesson_unit_ids=(),
                    request_id="req-cross-project-target",
                )
        assert caught.value.code == "LESSON_FANOUT_INVALID"
        session.rollback()
        assert session.scalar(select(func.count()).select_from(BranchRun)) == 0
        assert session.scalar(select(func.count()).select_from(NodeRun)) == 0


def test_fanout_rejects_duplicate_or_overlapping_archive_ids(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor, run_id, lesson_id = _seed_lesson(session)
            target = _targets(session, actor, lesson_id)

        for targets, archived in (
            (target, (lesson_id,)),
            ((), (lesson_id, lesson_id)),
        ):
            with pytest.raises(ApiError) as caught:
                with session.begin():
                    LessonWorkflowFanoutService(session, actor).synchronize(
                        run_id,
                        targets=targets,
                        archived_lesson_unit_ids=archived,
                        request_id="req-invalid-archive-scope",
                    )
            assert caught.value.code == "LESSON_FANOUT_INVALID"
            session.rollback()

        assert session.scalar(select(func.count()).select_from(BranchRun)) == 0
        assert session.scalar(select(func.count()).select_from(NodeRun)) == 0


def test_branch_update_disables_existing_ready_entrypoint(
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
                request_id="req-branch-ready",
            )
            lesson = LessonRepository(session, actor).get(lesson_id)
            assert lesson is not None
            LessonService(session, actor).update_branches(
                lesson_id,
                expected_version=lesson.lock_version,
                changes={
                    BranchKey.INTRO_OPTIONS: BranchConfigurationChange(
                        enabled=False,
                        settings={},
                    )
                },
                request_id="req-disable-intro",
            )

        branch = session.scalar(select(BranchRun).where(BranchRun.branch_key == "intro_options"))
        node = session.scalar(select(NodeRun).where(NodeRun.node_key == "intro.generate_options"))
        assert branch is not None and branch.status == "disabled"
        assert node is not None and node.status == "disabled"


def test_active_entrypoint_blocks_disable_until_cancelled_then_retry_succeeds(
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
                request_id="req-branch-active",
            )
            node = session.scalar(
                select(NodeRun).where(NodeRun.node_key == "intro.generate_options")
            )
            lesson = LessonRepository(session, actor).get(lesson_id)
            assert node is not None and lesson is not None
            node.status = "queued"
            expected_version = lesson.lock_version

        with pytest.raises(ApiError) as caught:
            with session.begin():
                LessonService(session, actor).update_branches(
                    lesson_id,
                    expected_version=expected_version,
                    changes={
                        BranchKey.INTRO_OPTIONS: BranchConfigurationChange(
                            enabled=False,
                            settings={},
                        )
                    },
                    request_id="req-disable-active",
                )
        assert caught.value.code == "LESSON_BRANCH_EXECUTION_ACTIVE"
        session.rollback()

        with session.begin():
            locked = session.get(NodeRun, node.id)
            lesson = LessonRepository(session, actor).get(lesson_id)
            assert locked is not None and lesson is not None
            locked.status = "cancelled"
            LessonService(session, actor).update_branches(
                lesson_id,
                expected_version=lesson.lock_version,
                changes={
                    BranchKey.INTRO_OPTIONS: BranchConfigurationChange(
                        enabled=False,
                        settings={},
                    )
                },
                request_id="req-disable-cancelled",
            )

        branch = session.scalar(select(BranchRun).where(BranchRun.branch_key == "intro_options"))
        latest = session.scalar(
            select(NodeRun)
            .where(NodeRun.node_key == "intro.generate_options")
            .order_by(NodeRun.run_no.desc())
            .limit(1)
        )
        assert branch is not None and branch.status == "disabled"
        assert latest is not None and latest.status == "cancelled"


def test_execution_context_rejects_ready_node_on_disabled_branch(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor, run_id, lesson_id = _seed_lesson(session)
        LessonWorkflowFanoutService(session, actor).synchronize(
            run_id,
            targets=_targets(session, actor, lesson_id),
            archived_lesson_unit_ids=(),
            request_id="req-disabled-execution",
        )
        branch = session.scalar(select(BranchRun).where(BranchRun.branch_key == "intro_options"))
        node = session.scalar(select(NodeRun).where(NodeRun.node_key == "intro.generate_options"))
        assert branch is not None and node is not None
        branch.status = "disabled"

        with pytest.raises(WorkflowExecutionPortError) as caught:
            SqlAlchemyWorkflowExecutionPort(session, actor).require_context(
                node.id,
                for_update=True,
            )
        assert caught.value.code == "NODE_EXECUTION_BRANCH_DISABLED"


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
