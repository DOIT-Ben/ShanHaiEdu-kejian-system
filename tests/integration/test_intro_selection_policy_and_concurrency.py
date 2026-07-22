from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.context import system_actor
from apps.api.intro_selections.models import IntroSelection
from apps.api.intro_selections.service import IntroSelectionService
from apps.api.workflows.service import WorkflowRuntimeService
from tests.integration.intro_selection_support import (
    ApprovedOptionSet,
    prepare_approved_option_set,
    set_select_policy_snapshot,
)
from workflow.node_state import NodeStatus


async def test_policy_default_requires_explicit_exact_rule_and_unique_highest_score(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await prepare_approved_option_set(factory)
    denied = (
        ("automatic", [], "mode-only"),
        ("automatic", [{"node_key": "intro.select", "auto_approve": True}], "other-action"),
        ("guided", [{"node_key": "intro.select", "auto_select": False}], "explicit-deny"),
        ("automatic", [{"node_key": "*", "auto_select": True}], "wildcard"),
    )
    for index, (mode, rules, suffix) in enumerate(denied, start=2):
        set_select_policy_snapshot(
            factory,
            prepared,
            mode=mode,
            node_rules=rules,
            policy_version=index,
        )
        with factory() as session:
            with pytest.raises(ApiError), session.begin():
                IntroSelectionService(
                    session,
                    system_actor(prepared.actor.organization_id),
                ).select_policy_default(
                    project_id=prepared.project_id,
                    lesson_unit_id=prepared.lesson_unit_id,
                    artifact_version_id=prepared.version_id,
                    node_run_id=prepared.select_node_run_id,
                    reason="Policy matrix denial.",
                    idempotency_key=f"issue-128-policy-{suffix}",
                    ttl_seconds=3600,
                )

    set_select_policy_snapshot(
        factory,
        prepared,
        mode="guided",
        node_rules=[{"node_key": "intro.select", "auto_select": True}],
        policy_version=9,
    )
    with factory() as session, session.begin():
        selected = IntroSelectionService(
            session,
            system_actor(prepared.actor.organization_id),
        ).select_policy_default(
            project_id=prepared.project_id,
            lesson_unit_id=prepared.lesson_unit_id,
            artifact_version_id=prepared.version_id,
            node_run_id=prepared.select_node_run_id,
            reason="Use the unique highest recommendation.",
            idempotency_key="issue-128-policy-allowed",
            ttl_seconds=3600,
        )
        assert selected.selection_method == "policy_default"
        assert selected.actor_type == "system"
        assert selected.actor_user_id is None
        assert selected.policy_evidence["policy_version"] == 9
        assert selected.policy_evidence["auto_select"] is True
        assert selected.recommendation_evidence["unique_highest"] is True
        assert selected.option_key == selected.recommendation_evidence["option_key"]

    with factory() as session, session.begin():
        WorkflowRuntimeService(
            session,
            system_actor(prepared.actor.organization_id),
        ).transition_node(prepared.select_node_run_id, NodeStatus.DISABLED)
    with factory() as session:
        with pytest.raises(ApiError), session.begin():
            IntroSelectionService(
                session,
                system_actor(prepared.actor.organization_id),
            ).select_policy_default(
                project_id=prepared.project_id,
                lesson_unit_id=prepared.lesson_unit_id,
                artifact_version_id=prepared.version_id,
                node_run_id=prepared.select_node_run_id,
                reason="Use the unique highest recommendation.",
                idempotency_key="issue-128-policy-allowed",
                ttl_seconds=3600,
            )


async def test_concurrent_double_selection_keeps_one_active_and_all_history(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    prepared = await prepare_approved_option_set(factory)
    barrier = Barrier(2)

    def choose(index: int) -> str:
        barrier.wait(timeout=30)
        with factory() as session, session.begin():
            selected = IntroSelectionService(session, prepared.actor).select_teacher(
                project_id=prepared.project_id,
                lesson_unit_id=prepared.lesson_unit_id,
                artifact_version_id=prepared.version_id,
                option_key=prepared.option_keys[index],
                reason=f"Concurrent teacher choice {index}.",
                idempotency_key=f"issue-128-concurrent-{index}",
                ttl_seconds=3600,
            )
            return str(selected.id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(choose, index) for index in range(2)]
        selection_ids = {future.result(timeout=60) for future in futures}

    with factory() as session:
        assert len(selection_ids) == 2
        assert _count(session, prepared, active=None) == 2
        assert _count(session, prepared, active=True) == 1
        assert _count(session, prepared, active=False) == 1


def _count(
    session: Session,
    prepared: ApprovedOptionSet,
    *,
    active: bool | None,
) -> int:
    statement = (
        select(func.count())
        .select_from(IntroSelection)
        .where(IntroSelection.lesson_unit_id == prepared.lesson_unit_id)
    )
    if active is not None:
        statement = statement.where(IntroSelection.active.is_(active))
    return int(session.scalar(statement) or 0)
