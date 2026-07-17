from __future__ import annotations

from uuid import UUID

import httpx
import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from apps.api.content_runtime.registry import BUILTIN_RUNTIME_DEFAULTS
from apps.api.database import build_engine, build_session_factory
from apps.api.main import create_app
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.settings import Settings
from apps.api.workflows.models import NodeInputSnapshot, NodeRun, WorkflowRun
from apps.api.workflows.service import WorkflowRuntimeError, WorkflowRuntimeService
from tests.conftest import run_migration
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.identity import configure_test_identity, seed_test_actor
from workflow.node_state import NodeStatus


def test_workflow_runtime_enforces_single_active_run_and_project_versions(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
            run = WorkflowRuntimeService(session, actor).start_project_run(project.id)

        assert run.content_release_id == project.content_release_id
        assert run.workflow_definition_version_id == project.workflow_definition_version_id
        with pytest.raises(WorkflowRuntimeError, match="active"):
            with session.begin():
                WorkflowRuntimeService(session, actor).start_project_run(project.id)

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                WorkflowRun(
                    id=UUID("01980000-0000-7000-8000-000000000099"),
                    organization_id=actor.organization_id,
                    project_id=project.id,
                    workflow_definition_version_id=(
                        BUILTIN_RUNTIME_DEFAULTS.workflow_definition_version_id
                    ),
                    content_release_id=BUILTIN_RUNTIME_DEFAULTS.content_release_id,
                    automation_policy_snapshot_json={},
                    run_no=2,
                    status="paused",
                    current_event_seq=0,
                    created_by=actor.principal_id,
                    updated_by=actor.principal_id,
                )
            )
            session.flush()


def test_node_transition_and_input_snapshot_are_append_only(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            actor = seed_test_actor(session)
            project = ProjectRepository(session, actor).create(
                CreateProjectRequest(title="Fractions", knowledge_point="One half")
            )
            run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
            with pytest.raises(WorkflowRuntimeError, match="not declared"):
                WorkflowRuntimeService(session, actor).create_project_node_run(
                    run.id,
                    node_key="unknown",
                    status=NodeStatus.READY,
                )
            with pytest.raises(WorkflowRuntimeError, match="initial status"):
                WorkflowRuntimeService(session, actor).create_project_node_run(
                    run.id,
                    node_key="prepare",
                    status=NodeStatus.APPROVED,
                )
            node = WorkflowRuntimeService(session, actor).create_project_node_run(
                run.id,
                node_key="prepare",
                status=NodeStatus.READY,
            )
            snapshot = WorkflowRuntimeService(session, actor).add_input_snapshot(
                node.id,
                input_key="project",
                source_type="project",
                source_id=project.id,
                source_version_id=None,
                content_hash="d" * 64,
                snapshot={"knowledge_point": "One half"},
            )
            WorkflowRuntimeService(session, actor).transition_node(
                node.id,
                NodeStatus.QUEUED,
            )

        with session.begin_nested():
            waiting = WorkflowRuntimeService(session, actor).create_project_node_run(
                run.id,
                node_key="prepare",
                status=NodeStatus.READY,
            )

        with pytest.raises(WorkflowRuntimeError, match="active execution"):
            with session.begin_nested():
                WorkflowRuntimeService(session, actor).transition_node(
                    waiting.id,
                    NodeStatus.RUNNING,
                )

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                NodeRun(
                    id=UUID("01980000-0000-7000-8000-000000000098"),
                    organization_id=actor.organization_id,
                    workflow_run_id=run.id,
                    branch_run_id=None,
                    node_key="prepare",
                    run_no=2,
                    status="running",
                    trigger_type="retry",
                    automation_policy_snapshot_json={},
                    created_by=actor.principal_id,
                    updated_by=actor.principal_id,
                )
            )
            session.flush()

        with pytest.raises(WorkflowRuntimeError, match="invalid node transition"):
            with session.begin_nested():
                WorkflowRuntimeService(session, actor).transition_node(
                    node.id,
                    NodeStatus.APPROVED,
                )

        with pytest.raises(DBAPIError), session.begin_nested():
            persisted = session.get(NodeInputSnapshot, snapshot.id)
            assert persisted is not None
            persisted.snapshot_json = {"knowledge_point": "changed"}
            session.flush()

        persisted_node = session.get(NodeRun, node.id)
        assert persisted_node is not None and persisted_node.status == NodeStatus.QUEUED


async def test_project_workflow_aggregate_matches_contract(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    app = create_app(
        settings=Settings(
            _env_file=None,
            environment="test",
            database_url=postgres_database_url,
        )
    )
    actor = configure_test_identity(app)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "workflow-project-create-001"},
                json={"title": "Fractions", "knowledge_point": "One half"},
            )
            assert created.status_code == 201, created.text
            project_id = UUID(created.json()["data"]["id"])
            factory = build_session_factory(app.state.database_engine)
            with factory() as session, session.begin():
                run = WorkflowRuntimeService(session, actor).start_project_run(project_id)
                WorkflowRuntimeService(session, actor).create_project_node_run(
                    run.id,
                    node_key="prepare",
                    status=NodeStatus.READY,
                )

            response = await client.get(f"/api/v2/projects/{project_id}/workflow")

            assert response.status_code == 200, response.text
            assert_contract_response(response, operation_id="getProjectWorkflow", status="200")
            data = response.json()["data"]
            assert data["project"]["content_release_id"] == str(
                BUILTIN_RUNTIME_DEFAULTS.content_release_id
            )
            assert data["workflow_run"]["id"] == str(run.id)
            assert [node["node_key"] for node in data["node_runs"]] == ["prepare"]
    finally:
        app.state.database_engine.dispose()
