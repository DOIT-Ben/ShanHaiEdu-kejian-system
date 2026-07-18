from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from apps.api.database import build_engine, build_session_factory
from apps.api.projects.models import AutomationPolicy
from apps.api.projects.policy_schemas import UpdateAutomationPolicyRequest
from apps.api.projects.policy_service import AutomationPolicyService
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.service import WorkflowRuntimeService
from tests.fakes.identity import seed_test_actor


@pytest.mark.parametrize(
    ("legacy_mode", "expected_mode", "expects_disabled_actions"),
    [
        ("manual", "guided", True),
        ("assisted", "guided", False),
        ("automatic", "automatic", False),
    ],
)
def test_legacy_modes_create_versioned_policy_on_the_same_workflow(
    migrated_database_url: str,
    legacy_mode: str,
    expected_mode: str,
    expects_disabled_actions: bool,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(
                title="Fractions",
                knowledge_point="One half",
                automation_mode=legacy_mode,
            )
        )
        policy = AutomationPolicyService(session, actor).get(project.id)
        run = WorkflowRuntimeService(session, actor).start_project_run(project.id)

        assert policy.mode == expected_mode
        assert policy.workflow_definition_version_id == project.workflow_definition_version_id
        assert run.workflow_definition_version_id == project.workflow_definition_version_id
        assert run.automation_policy_snapshot_json["mode"] == expected_mode
        assert run.automation_policy_snapshot_json["policy_version"] == 1
        assert bool(policy.node_rules) is expects_disabled_actions
        if expects_disabled_actions:
            assert policy.node_rules[0].node_key == "*"
            assert policy.node_rules[0].auto_start is False


def test_current_execution_mode_is_mutually_exclusive_with_legacy_input() -> None:
    current = CreateProjectRequest(
        title="Fractions",
        knowledge_point="One half",
        execution_mode="automatic",
    )

    assert current.execution_mode == "automatic"
    assert current.automation_mode is None
    with pytest.raises(ValidationError):
        CreateProjectRequest(
            title="Fractions",
            knowledge_point="One half",
            execution_mode="guided",
            automation_mode="assisted",
        )


def test_policy_update_is_idempotent_and_never_changes_workflow_definition(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )

        payload = UpdateAutomationPolicyRequest(mode="automatic", node_rules=[])
        with session.begin():
            first = AutomationPolicyService(session, actor).update(
                project.id,
                payload,
                idempotency_key="policy-update-001",
                request_id="req-policy-update",
                ttl_seconds=3600,
            )
        with session.begin():
            replay = AutomationPolicyService(session, actor).update(
                project.id,
                payload,
                idempotency_key="policy-update-001",
                request_id="req-policy-update-replay",
                ttl_seconds=3600,
            )

        assert first.policy_version == replay.policy_version == 2
        assert first.workflow_definition_version_id == project.workflow_definition_version_id
        assert (
            session.scalar(
                select(func.count())
                .select_from(AutomationPolicy)
                .where(AutomationPolicy.project_id == project.id)
            )
            == 2
        )
