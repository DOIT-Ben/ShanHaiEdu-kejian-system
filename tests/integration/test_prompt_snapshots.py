from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

import httpx
import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from apps.api.database import build_engine, build_session_factory
from apps.api.ids import new_uuid7
from apps.api.main import create_app
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.prompt_runtime.models import ContextSnapshot, PromptSnapshot
from apps.api.prompt_runtime.service import PromptSnapshotError, PromptSnapshotService
from apps.api.settings import Settings
from apps.api.workflows.models import NodeRun
from apps.api.workflows.service import WorkflowRuntimeService
from tests.contract.test_stage0_resources import assert_contract_response
from tests.fakes.identity import configure_test_identity, seed_test_actor
from workflow.node_state import NodeStatus
from workflow.prompt_runtime import (
    ContextBinding,
    ContextItem,
    PromptSection,
    assemble_context,
    compile_prompt,
)


def test_context_and_prompt_snapshots_are_unique_and_append_only_per_node(
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
            node = WorkflowRuntimeService(session, actor).create_project_node_run(
                run.id,
                node_key="prepare",
                status=NodeStatus.READY,
            )
            context = ContextSnapshot(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                project_id=project.id,
                node_run_id=node.id,
                bindings_json={"bindings": []},
                content_hash="a" * 64,
                created_by=actor.principal_id,
            )
            prompt = PromptSnapshot(
                id=new_uuid7(),
                organization_id=actor.organization_id,
                project_id=project.id,
                node_run_id=node.id,
                context_snapshot_id=context.id,
                template_refs_json={"template_key": "lesson-plan.prompt", "version": "1.0.0"},
                layers_json={"layers": []},
                editable_prompt="Visible business prompt",
                user_diff_json={},
                compiled_prompt="Protected compiled prompt",
                request_schema_json={"type": "object"},
                preview_json={
                    "editable_prompt": "Visible business prompt",
                    "locked_layers": [],
                    "context_summary": [],
                    "schema": {"type": "object"},
                },
                content_hash="b" * 64,
                created_by=actor.principal_id,
            )
            session.add_all((context, prompt))

        assert prompt.context_snapshot_id == context.id

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                ContextSnapshot(
                    id=new_uuid7(),
                    organization_id=actor.organization_id,
                    project_id=project.id,
                    node_run_id=node.id,
                    bindings_json={"bindings": []},
                    content_hash="c" * 64,
                    created_by=actor.principal_id,
                )
            )
            session.flush()

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                ContextSnapshot(
                    id=new_uuid7(),
                    organization_id=actor.organization_id,
                    project_id=project.id,
                    node_run_id=new_uuid7(),
                    bindings_json={"bindings": []},
                    content_hash="d" * 64,
                    created_by=actor.principal_id,
                )
            )
            session.flush()

        with pytest.raises(DBAPIError), session.begin_nested():
            persisted = session.get(ContextSnapshot, context.id)
            assert persisted is not None
            persisted.bindings_json = {"bindings": [{"source": "changed"}]}
            session.flush()

        with pytest.raises(DBAPIError), session.begin_nested():
            persisted_prompt = session.get(PromptSnapshot, prompt.id)
            assert persisted_prompt is not None
            session.delete(persisted_prompt)
            session.flush()


def test_snapshot_hashes_and_foreign_keys_are_database_enforced(
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
            node = WorkflowRuntimeService(session, actor).create_project_node_run(
                run.id,
                node_key="prepare",
                status=NodeStatus.READY,
            )

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                ContextSnapshot(
                    id=new_uuid7(),
                    organization_id=actor.organization_id,
                    project_id=project.id,
                    node_run_id=node.id,
                    bindings_json={"bindings": []},
                    content_hash="not-a-hash",
                    created_by=actor.principal_id,
                )
            )
            session.flush()


def test_snapshot_service_is_idempotent_and_never_overwrites_frozen_prompt(
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
            node = WorkflowRuntimeService(session, actor).create_project_node_run(
                run.id,
                node_key="prepare",
                status=NodeStatus.READY,
            )
            context, compiled = compiled_fixture()
            first = PromptSnapshotService(session, actor).freeze(
                node.id,
                context=context,
                prompt=compiled,
            )
            second = PromptSnapshotService(session, actor).freeze(
                node.id,
                context=context,
                prompt=compiled,
            )

        assert second.context.id == first.context.id
        assert second.prompt.id == first.prompt.id
        assert "PLATFORM_PRIVATE" not in json.dumps(first.prompt.preview_json)
        assert "CONTEXT_PRIVATE" not in json.dumps(first.prompt.preview_json)
        assert "PROVIDER_PRIVATE" not in json.dumps(first.prompt.preview_json)

        with session.begin():
            WorkflowRuntimeService(session, actor).transition_node(
                node.id,
                NodeStatus.QUEUED,
            )
            retried = PromptSnapshotService(session, actor).freeze(
                node.id,
                context=context,
                prompt=compiled,
            )
        assert retried.prompt.id == first.prompt.id

        changed = compile_prompt(
            template_key="lesson-plan.prompt",
            template_version="1.0.1",
            platform_safety="PLATFORM_PRIVATE",
            sections=(PromptSection("task", "task", "Changed task.", True, True),),
            context=context,
            output_schema={"type": "object"},
            provider_format="PROVIDER_PRIVATE",
            user_edit_mode="replace_editable_layer",
            user_edit_max_chars=60_000,
        )
        with pytest.raises(PromptSnapshotError) as caught, session.begin_nested():
            PromptSnapshotService(session, actor).freeze(
                node.id,
                context=context,
                prompt=changed,
            )
        assert caught.value.code == "PROMPT_SNAPSHOT_ALREADY_FROZEN"


def test_prompt_freeze_serializes_with_node_execution_start(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
        node = WorkflowRuntimeService(session, actor).create_project_node_run(
            run.id,
            node_key="prepare",
            status=NodeStatus.READY,
        )
        context, compiled = compiled_fixture()

    def freeze() -> None:
        with factory() as worker_session, worker_session.begin():
            PromptSnapshotService(worker_session, actor).freeze(
                node.id,
                context=context,
                prompt=compiled,
            )

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        with factory() as locker, locker.begin():
            locked_node = locker.get(NodeRun, node.id, with_for_update=True)
            assert locked_node is not None
            locked_node.status = NodeStatus.QUEUED.value
            locker.flush()
            future = executor.submit(freeze)
            with pytest.raises(FutureTimeoutError):
                future.result(timeout=0.5)

        with pytest.raises(PromptSnapshotError) as frozen:
            future.result(timeout=5)
        assert frozen.value.code == "PROMPT_SNAPSHOT_NODE_FROZEN"
    finally:
        executor.shutdown(wait=True)


async def test_prompt_preview_endpoint_returns_only_the_safe_projection(
    postgres_database_url: str,
) -> None:
    from tests.conftest import run_migration

    run_migration(postgres_database_url, "head")
    app = create_app(
        settings=Settings.model_validate(
            {
                "environment": "test",
                "database_url": postgres_database_url,
            }
        )
    )
    actor = configure_test_identity(app)
    factory = build_session_factory(app.state.database_engine)
    with factory() as session, session.begin():
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        run = WorkflowRuntimeService(session, actor).start_project_run(project.id)
        node = WorkflowRuntimeService(session, actor).create_project_node_run(
            run.id,
            node_key="prepare",
            status=NodeStatus.READY,
        )
        context_snapshot = ContextSnapshot(
            id=new_uuid7(),
            organization_id=actor.organization_id,
            project_id=project.id,
            node_run_id=node.id,
            bindings_json={"bindings": [{"source": "CONTEXT_PRIVATE"}]},
            content_hash="a" * 64,
            created_by=actor.principal_id,
        )
        prompt_snapshot = PromptSnapshot(
            id=new_uuid7(),
            organization_id=actor.organization_id,
            project_id=project.id,
            node_run_id=node.id,
            context_snapshot_id=context_snapshot.id,
            template_refs_json={
                "template_key": "lesson-plan.prompt",
                "template_version": "1.0.0",
            },
            layers_json={"layers": [{"content": "INTERNAL_METHOD_PRIVATE"}]},
            editable_prompt="Visible task.",
            user_diff_json={"mode": "replace_editable_layer"},
            compiled_prompt="PLATFORM_PRIVATE\nINTERNAL_METHOD_PRIVATE\nPROVIDER_PRIVATE",
            request_schema_json={"type": "object", "required": ["fixed_structure"]},
            preview_json={
                "editable_prompt": "Visible task.",
                "locked_layers": [
                    {"layer": "output_schema", "key": "request_schema", "locked": True}
                ],
                "context_summary": [
                    {
                        "binding_key": "preferences",
                        "source": "project.teacher_preferences",
                        "exposure": "hidden",
                        "item_count": 1,
                        "content_hash": "c" * 64,
                    }
                ],
                "schema": {"type": "object", "required": ["fixed_structure"]},
                "output_schema": {"private": True},
                "internal_prompt": "INTERNAL_METHOD_PRIVATE",
            },
            content_hash="b" * 64,
            created_by=actor.principal_id,
        )
        session.add_all((context_snapshot, prompt_snapshot))

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v2/node-runs/{node.id}/prompt-preview")

        assert response.status_code == 200, response.text
        assert_contract_response(response, operation_id="getPromptPreview", status="200")
        data = response.json()["data"]
        assert set(data) == {
            "prompt_snapshot_id",
            "content_hash",
            "editable_prompt",
            "edit_policy",
        }
        assert data["prompt_snapshot_id"] == str(prompt_snapshot.id)
        assert data["content_hash"] == prompt_snapshot.content_hash
        assert data["editable_prompt"] == prompt_snapshot.editable_prompt
        assert data["edit_policy"] == {
            "mode": "replace_editable_layer",
            "max_chars": 100_000,
        }
        rendered = json.dumps(data)
        assert "PLATFORM_PRIVATE" not in rendered
        assert "CONTEXT_PRIVATE" not in rendered
        assert "PROVIDER_PRIVATE" not in rendered
        assert "INTERNAL_METHOD_PRIVATE" not in rendered
        assert "fixed_structure" not in rendered

        with factory() as session:
            persisted = session.get(PromptSnapshot, prompt_snapshot.id)
            persisted_context = session.get(ContextSnapshot, context_snapshot.id)
            assert persisted is not None and persisted_context is not None
            assert persisted.layers_json == prompt_snapshot.layers_json
            assert persisted.compiled_prompt == prompt_snapshot.compiled_prompt
            assert persisted.request_schema_json == prompt_snapshot.request_schema_json
            assert persisted.content_hash == prompt_snapshot.content_hash
            assert persisted_context.bindings_json == context_snapshot.bindings_json
    finally:
        app.state.database_engine.dispose()


def compiled_fixture():
    context = assemble_context(
        (
            ContextBinding(
                binding_key="preferences",
                source="project.teacher_preferences",
                required=True,
                exposure="hidden",
                max_items=1,
                max_bytes=1_000,
            ),
        ),
        {
            "project.teacher_preferences": (
                ContextItem(
                    source="project.teacher_preferences",
                    source_id="preference-1",
                    source_version_id="preference-v1",
                    content={"text": "CONTEXT_PRIVATE"},
                ),
            )
        },
    )
    compiled = compile_prompt(
        template_key="lesson-plan.prompt",
        template_version="1.0.0",
        platform_safety="PLATFORM_PRIVATE",
        sections=(PromptSection("task", "task", "Visible task.", True, True),),
        context=context,
        output_schema={"type": "object"},
        provider_format="PROVIDER_PRIVATE",
        user_edit_mode="replace_editable_layer",
        user_edit_max_chars=60_000,
    )
    return context, compiled
