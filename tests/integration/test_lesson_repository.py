from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.ids import new_uuid7
from apps.api.lessons.domain import (
    ApprovedLessonDivision,
    ApprovedLessonItem,
    BranchConfigurationChange,
    BranchKey,
)
from apps.api.lessons.models import LessonBranchConfig, LessonUnit
from apps.api.lessons.repository import LessonRepository
from apps.api.lessons.service import LessonService
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.models import EventStreamEntry, OutboxEvent
from tests.fakes.identity import seed_test_actor

DIVISION_V1 = UUID("01920000-0000-7000-8000-000000000001")
DIVISION_V2 = UUID("01920000-0000-7000-8000-000000000002")


def division(
    version_id: UUID,
    *items: tuple[str, int, str],
) -> ApprovedLessonDivision:
    return ApprovedLessonDivision(
        version_id=version_id,
        lessons=tuple(
            ApprovedLessonItem(
                lesson_key=lesson_key,
                position=position,
                title=title,
                scope_summary=f"Scope for {title}",
                objective_summary=f"Objective for {title}",
                estimated_minutes=40,
            )
            for lesson_key, position, title in items
        ),
    )


def create_project(session, actor):
    return ProjectRepository(session, actor).create(
        CreateProjectRequest(title="Fractions", knowledge_point="One half")
    )


def test_approved_division_sync_is_idempotent_and_creates_default_branches(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = create_project(session, actor)
            service = LessonService(session, actor)
            first = service.synchronize_approved_division(
                project.id,
                division(
                    DIVISION_V1,
                    ("lesson-01", 1, "What is one half?"),
                    ("lesson-02", 2, "Compare fractions"),
                ),
                request_id="req_sync_1",
            )
            project_version = project.lock_version

        first_ids = [lesson.id for lesson in first]
        with session.begin():
            replay = LessonService(session, actor).synchronize_approved_division(
                project.id,
                division(
                    DIVISION_V1,
                    ("lesson-01", 1, "What is one half?"),
                    ("lesson-02", 2, "Compare fractions"),
                ),
                request_id="req_sync_2",
            )

        assert [lesson.id for lesson in replay] == first_ids
        assert project.lock_version == project_version
        assert session.scalar(select(func.count()).select_from(LessonUnit)) == 2
        assert session.scalar(select(func.count()).select_from(LessonBranchConfig)) == 8
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 1

        for lesson in first:
            configs = LessonRepository(session, actor).list_branch_configs(lesson.id)
            assert {BranchKey(config.branch_key): config.enabled for config in configs} == {
                BranchKey.LESSON_PLAN: True,
                BranchKey.INTRO_OPTIONS: True,
                BranchKey.PPT: False,
                BranchKey.VIDEO: False,
            }


def test_new_division_reorders_reuses_adds_and_archives_without_position_conflicts(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = create_project(session, actor)
            service = LessonService(session, actor)
            initial = service.synchronize_approved_division(
                project.id,
                division(
                    DIVISION_V1,
                    ("lesson-01", 1, "First"),
                    ("lesson-02", 2, "Second"),
                ),
                request_id="req_initial",
            )
            initial_ids = {lesson.lesson_key: lesson.id for lesson in initial}

        with session.begin():
            updated = LessonService(session, actor).synchronize_approved_division(
                project.id,
                division(
                    DIVISION_V2,
                    ("lesson-02", 1, "Second revised"),
                    ("lesson-03", 2, "Third"),
                ),
                request_id="req_updated",
            )

        assert [(item.lesson_key, item.position, item.status) for item in updated] == [
            ("lesson-02", 1, "active"),
            ("lesson-03", 2, "active"),
        ]
        all_lessons = LessonRepository(session, actor).list_for_project(
            project.id,
            include_archived=True,
        )
        by_key = {lesson.lesson_key: lesson for lesson in all_lessons}
        assert by_key["lesson-02"].id == initial_ids["lesson-02"]
        assert by_key["lesson-02"].title == "Second revised"
        assert by_key["lesson-03"].status == "active"
        assert by_key["lesson-01"].status == "archived"
        assert by_key["lesson-01"].position == 3
        assert len({lesson.position for lesson in all_lessons}) == 3


def test_branch_updates_use_lesson_lock_and_keep_lesson_plan_required(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = create_project(session, actor)
            lesson = LessonService(session, actor).synchronize_approved_division(
                project.id,
                division(DIVISION_V1, ("lesson-01", 1, "First")),
                request_id="req_sync",
            )[0]
            lesson_id = lesson.id

        with session.begin():
            updated = LessonService(session, actor).update_branches(
                lesson_id,
                expected_version=1,
                changes={BranchKey.PPT: BranchConfigurationChange(enabled=True, settings={})},
                request_id="req_branch",
            )
        assert updated.lock_version == 2
        configs = LessonRepository(session, actor).list_branch_configs(lesson_id)
        assert next(config for config in configs if config.branch_key == "ppt").enabled is True
        session.rollback()

        with pytest.raises(ApiError) as stale_error:
            with session.begin():
                LessonService(session, actor).update_branches(
                    lesson_id,
                    expected_version=1,
                    changes={BranchKey.VIDEO: BranchConfigurationChange(enabled=True, settings={})},
                    request_id="req_stale",
                )
        assert stale_error.value.code == "EDIT_CONFLICT"

        with pytest.raises(ApiError) as required_error:
            with session.begin():
                LessonService(session, actor).update_branches(
                    lesson_id,
                    expected_version=2,
                    changes={
                        BranchKey.LESSON_PLAN: BranchConfigurationChange(
                            enabled=False,
                            settings={},
                        )
                    },
                    request_id="req_required",
                )
        assert required_error.value.code == "LESSON_PLAN_REQUIRED"


def test_postgres_enforces_lesson_identity_position_and_required_branch_constraints(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = create_project(session, actor)
            lesson = LessonService(session, actor).synchronize_approved_division(
                project.id,
                division(DIVISION_V1, ("lesson-01", 1, "First")),
                request_id="req_constraints",
            )[0]

        def duplicate(*, lesson_key: str, position: int) -> LessonUnit:
            return LessonUnit(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                project_id=project.id,
                lesson_key=lesson_key,
                position=position,
                title="Duplicate",
                scope_summary="Scope",
                objective_summary="Objective",
                estimated_minutes=40,
                source_division_version_id=DIVISION_V2,
                status="active",
                created_by=actor.principal_id,
                updated_by=actor.principal_id,
            )

        for candidate in (
            duplicate(lesson_key="lesson-01", position=2),
            duplicate(lesson_key="lesson-02", position=1),
            duplicate(lesson_key="lesson-03", position=0),
        ):
            with pytest.raises(IntegrityError), session.begin_nested():
                session.add(candidate)
                session.flush()

        lesson_plan = next(
            config
            for config in LessonRepository(session, actor).list_branch_configs(lesson.id)
            if config.branch_key == "lesson_plan"
        )
        with pytest.raises(IntegrityError), session.begin_nested():
            lesson_plan.enabled = False
            session.flush()
