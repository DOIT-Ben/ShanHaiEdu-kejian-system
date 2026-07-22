from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from apps.api.artifacts.models import Artifact
from apps.api.artifacts.service import ArtifactService
from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.models import Organization, ProjectMember
from apps.api.ids import new_uuid7
from apps.api.intro_selections.models import IntroSelection
from apps.api.intro_selections.service import IntroSelectionService
from apps.api.lessons.models import LessonUnit
from tests.fakes.identity import seed_test_actor
from tests.integration.intro_selection_support import prepare_approved_option_set
from tests.integration.test_intro_option_runtime import (
    _generate_default_nine,  # pyright: ignore[reportPrivateUsage]
    _open_gate,  # pyright: ignore[reportPrivateUsage]
    _validate,  # pyright: ignore[reportPrivateUsage]
)


async def test_teacher_selection_reselects_without_mutating_history_or_snapshot(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await prepare_approved_option_set(factory)
    with factory() as session, session.begin():
        service = IntroSelectionService(session, prepared.actor)
        first = service.select_teacher(
            project_id=prepared.project_id,
            lesson_unit_id=prepared.lesson_unit_id,
            artifact_version_id=prepared.version_id,
            option_key=prepared.option_keys[0],
            reason="Teacher prefers the science hook.",
            idempotency_key="issue-128-teacher-first",
            ttl_seconds=3600,
        )
        original_snapshot = deepcopy(first.snapshot)
        first.snapshot["title"] = "Mutated response copy"

    with factory() as session, session.begin():
        service = IntroSelectionService(session, prepared.actor)
        second = service.select_teacher(
            project_id=prepared.project_id,
            lesson_unit_id=prepared.lesson_unit_id,
            artifact_version_id=prepared.version_id,
            option_key=prepared.option_keys[1],
            reason="Teacher changed the classroom hook.",
            idempotency_key="issue-128-teacher-second",
            ttl_seconds=3600,
        )
        replay = service.select_teacher(
            project_id=prepared.project_id,
            lesson_unit_id=prepared.lesson_unit_id,
            artifact_version_id=prepared.version_id,
            option_key=prepared.option_keys[0],
            reason="Teacher prefers the science hook.",
            idempotency_key="issue-128-teacher-first",
            ttl_seconds=3600,
        )

    with factory() as session:
        rows = list(
            session.scalars(
                select(IntroSelection)
                .where(IntroSelection.lesson_unit_id == prepared.lesson_unit_id)
                .order_by(IntroSelection.selected_at)
            )
        )
        assert len(rows) == 2
        assert [row.active for row in rows] == [False, True]
        assert rows[0].id == first.id == replay.id
        assert rows[1].id == second.id
        assert replay.active is False
        assert rows[0].snapshot_json == original_snapshot
        assert rows[0].actor_type == "user"
        assert rows[0].actor_user_id == prepared.actor.user_id

    with factory() as session:
        with pytest.raises(DBAPIError), session.begin():
            session.execute(
                update(IntroSelection)
                .where(IntroSelection.id == first.id)
                .values(snapshot_json={"option_key": prepared.option_keys[0]})
            )
    with factory() as session:
        with pytest.raises(DBAPIError), session.begin():
            session.execute(
                update(IntroSelection)
                .where(IntroSelection.id == first.id)
                .values(active=True, deactivated_at=None, deactivated_by=None)
            )


async def test_every_new_or_replayed_teacher_command_reauthorizes(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await prepare_approved_option_set(factory)
    with factory() as session, session.begin():
        IntroSelectionService(session, prepared.actor).select_teacher(
            project_id=prepared.project_id,
            lesson_unit_id=prepared.lesson_unit_id,
            artifact_version_id=prepared.version_id,
            option_key=prepared.option_keys[0],
            reason="Authorized initial choice.",
            idempotency_key="issue-128-reauthorize",
            ttl_seconds=3600,
        )
    with factory() as session, session.begin():
        member = session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == prepared.project_id,
                ProjectMember.user_id == prepared.actor.user_id,
            )
        )
        assert member is not None
        session.delete(member)

    with factory() as session:
        with pytest.raises(ApiError) as caught, session.begin():
            IntroSelectionService(session, prepared.actor).select_teacher(
                project_id=prepared.project_id,
                lesson_unit_id=prepared.lesson_unit_id,
                artifact_version_id=prepared.version_id,
                option_key=prepared.option_keys[0],
                reason="Authorized initial choice.",
                idempotency_key="issue-128-reauthorize",
                ttl_seconds=3600,
            )
    assert caught.value.status_code in {403, 404}


async def test_unapproved_wrong_lesson_wrong_option_and_cross_tenant_are_rejected(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    generated = await _generate_default_nine(factory)
    with factory() as session:
        with pytest.raises(ApiError), session.begin():
            IntroSelectionService(session, generated.actor).select_teacher(
                project_id=generated.project_id,
                lesson_unit_id=generated.lesson_unit_id,
                artifact_version_id=generated.version_id,
                option_key="INTRO-SCI-01",
                reason="Unapproved source must fail.",
                idempotency_key="issue-128-unapproved",
                ttl_seconds=3600,
            )

    _validate(factory, generated.actor, generated.version_id)
    _open_gate(factory, generated.actor, generated.version_id)
    with factory() as session, session.begin():
        ArtifactService(session, generated.actor).review(
            generated.version_id,
            action="approve",
            comment="Approve for negative selection tests.",
            request_id="issue-128-negative-approve",
        )
        source_lesson = session.get(LessonUnit, generated.lesson_unit_id)
        assert source_lesson is not None
        other_lesson = LessonUnit(
            id=new_uuid7(),
            organization_id=generated.actor.organization_id,
            project_id=generated.project_id,
            lesson_key="LESSON-OTHER",
            position=2,
            title="Other lesson",
            scope_summary="Other scope",
            objective_summary="Other objective",
            source_division_version_id=source_lesson.source_division_version_id,
            status="active",
            created_by=generated.actor.principal_id,
            updated_by=generated.actor.principal_id,
        )
        session.add(other_lesson)
        outsider_org_id = new_uuid7()
        session.add(
            Organization(
                id=outsider_org_id,
                slug=f"issue-128-{outsider_org_id.hex[:12]}",
                name="Issue 128 outsider",
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        outsider = seed_test_actor(
            session,
            organization_id=outsider_org_id,
            user_id=new_uuid7(),
            principal_id=new_uuid7(),
            member_id=new_uuid7(),
            email=f"{outsider_org_id.hex[:12]}@example.test",
        )

    invalid_commands = (
        (generated.actor, other_lesson.id, "INTRO-SCI-01", "wrong-lesson"),
        (generated.actor, generated.lesson_unit_id, "INTRO-SCI-99", "wrong-option"),
        (outsider, generated.lesson_unit_id, "INTRO-SCI-01", "cross-tenant"),
    )
    for actor, lesson_id, option_key, suffix in invalid_commands:
        with factory() as session:
            with pytest.raises(ApiError), session.begin():
                IntroSelectionService(session, actor).select_teacher(
                    project_id=generated.project_id,
                    lesson_unit_id=lesson_id,
                    artifact_version_id=generated.version_id,
                    option_key=option_key,
                    reason="Negative scope test.",
                    idempotency_key=f"issue-128-{suffix}",
                    ttl_seconds=3600,
                )


async def test_revoke_stale_and_reapproval_never_revive_an_old_selection(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await prepare_approved_option_set(factory)
    with factory() as session, session.begin():
        selected = IntroSelectionService(session, prepared.actor).select_teacher(
            project_id=prepared.project_id,
            lesson_unit_id=prepared.lesson_unit_id,
            artifact_version_id=prepared.version_id,
            option_key=prepared.option_keys[0],
            reason="Selection before source invalidation.",
            idempotency_key="issue-128-before-invalidation",
            ttl_seconds=3600,
        )
    with factory() as session, session.begin():
        artifact = session.get(Artifact, prepared.artifact_id)
        assert artifact is not None
        artifact.status = "stale"
        artifact.stale_reason_json = {"reason_code": "UPSTREAM_CHANGED"}
    with factory() as session:
        service = IntroSelectionService(session, prepared.actor)
        stale = service.get(selected.id)
        assert stale.active is True
        assert stale.consumable is False
        assert stale.unconsumable_reason == "source_stale"
        with pytest.raises(ApiError):
            service.current_consumable(
                project_id=prepared.project_id,
                lesson_unit_id=prepared.lesson_unit_id,
            )

    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="accept_stale",
            comment="Explicitly accept the stale source.",
            request_id="issue-128-accept-stale-source",
        )
    with factory() as session:
        service = IntroSelectionService(session, prepared.actor)
        restored = service.get(selected.id)
        assert restored.consumable is False
        assert restored.unconsumable_reason == "source_approval_changed"
        with pytest.raises(ApiError):
            service.current_consumable(
                project_id=prepared.project_id,
                lesson_unit_id=prepared.lesson_unit_id,
            )

    with factory() as session, session.begin():
        ArtifactService(session, prepared.actor).review(
            prepared.version_id,
            action="revoke",
            comment="Revoke the newly accepted source approval.",
            request_id="issue-128-revoke-source",
        )
    with factory() as session:
        service = IntroSelectionService(session, prepared.actor)
        revoked = service.get(selected.id)
        assert revoked.consumable is False
        assert revoked.unconsumable_reason == "source_approval_changed"
        with pytest.raises(ApiError):
            service.current_consumable(
                project_id=prepared.project_id,
                lesson_unit_id=prepared.lesson_unit_id,
            )
