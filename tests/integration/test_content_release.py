from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.exc import DBAPIError

from apps.api.content_runtime.models import (
    ContentDefinitionVersion,
    ContentPackage,
    ContentPackageVersion,
    ContentRelease,
    ContentReleaseItem,
)
from apps.api.content_runtime.registry import (
    BUILTIN_CONTENT_DEFINITION_VERSION_ID,
    BUILTIN_RUNTIME_DEFAULTS,
    RuntimeDefaults,
)
from apps.api.database import build_engine, build_session_factory, utc_now
from apps.api.ids import new_uuid7
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.workflows.models import WorkflowDefinition, WorkflowDefinitionVersion
from tests.fakes.identity import seed_test_actor


def test_builtin_release_and_workflow_are_published_and_project_is_pinned(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )

        release = session.get(ContentRelease, project.content_release_id)
        workflow = session.get(
            WorkflowDefinitionVersion,
            project.workflow_definition_version_id,
        )

        assert project.content_release_id == BUILTIN_RUNTIME_DEFAULTS.content_release_id
        assert (
            project.workflow_definition_version_id
            == BUILTIN_RUNTIME_DEFAULTS.workflow_definition_version_id
        )
        assert release is not None and release.status == "published"
        assert workflow is not None and workflow.status == "published"


def test_changing_runtime_defaults_only_affects_new_projects(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        request = CreateProjectRequest(title="Fractions", knowledge_point="One half")
        original = ProjectRepository(session, actor).create(request)
        alternate = seed_alternate_runtime(session, actor.principal_id)
        newer = ProjectRepository(session, actor, defaults=alternate).create(
            replace_request(request, title="Fractions two")
        )

        session.refresh(original)
        assert original.content_release_id == BUILTIN_RUNTIME_DEFAULTS.content_release_id
        assert (
            original.workflow_definition_version_id
            == BUILTIN_RUNTIME_DEFAULTS.workflow_definition_version_id
        )
        assert newer.content_release_id == alternate.content_release_id
        assert newer.workflow_definition_version_id == alternate.workflow_definition_version_id


def test_postgres_rejects_published_runtime_mutation(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with session.begin():
            seed_test_actor(session)

        targets = (
            (ContentRelease, BUILTIN_RUNTIME_DEFAULTS.content_release_id, "name", "changed"),
            (
                ContentDefinitionVersion,
                BUILTIN_CONTENT_DEFINITION_VERSION_ID,
                "schema_json",
                {"type": "string"},
            ),
            (
                WorkflowDefinitionVersion,
                BUILTIN_RUNTIME_DEFAULTS.workflow_definition_version_id,
                "graph_json",
                {"nodes": []},
            ),
        )
        for model, identity, field, value in targets:
            with pytest.raises(DBAPIError), session.begin_nested():
                record = session.get(model, identity)
                assert record is not None
                setattr(record, field, value)
                session.flush()


def replace_request(request: CreateProjectRequest, *, title: str) -> CreateProjectRequest:
    return request.model_copy(update={"title": title})


def seed_alternate_runtime(session, principal_id: UUID) -> RuntimeDefaults:
    package = ContentPackage(
        id=new_uuid7(),
        package_key="builtin.primary-math.alternate",
        name="Alternate primary math runtime",
        package_type="builtin",
        owner_scope="platform",
        status="active",
    )
    package_version = ContentPackageVersion(
        id=new_uuid7(),
        content_package_id=package.id,
        semantic_version="2.0.0",
        runtime_constraint=">=0.1.0",
        manifest_json={"kind": "test"},
        checksum="a" * 64,
        status="draft",
        validated_at=utc_now(),
        published_at=None,
    )
    release = ContentRelease(
        id=new_uuid7(),
        release_key="builtin-primary-math-alternate",
        name="Alternate primary math release",
        status="draft",
        published_at=None,
        published_by=None,
        notes=None,
    )
    release_item = ContentReleaseItem(
        id=new_uuid7(),
        content_release_id=release.id,
        content_package_version_id=package_version.id,
        mount_key="primary_math",
        priority=100,
    )
    definition = ContentDefinitionVersion(
        id=new_uuid7(),
        definition_key="lesson_plan",
        content_package_version_id=package_version.id,
        schema_json={"type": "object"},
        ui_schema_json={},
        export_mapping_json={},
        validation_rules_json={},
        checksum="b" * 64,
    )
    workflow = WorkflowDefinition(
        id=new_uuid7(),
        workflow_key="primary_math.alternate",
        name="Alternate primary math workflow",
        domain="primary_math",
        status="active",
    )
    workflow_version = WorkflowDefinitionVersion(
        id=new_uuid7(),
        workflow_definition_id=workflow.id,
        version_no=2,
        graph_json={"nodes": []},
        input_contract_json={},
        status="published",
        checksum="c" * 64,
        published_at=utc_now(),
    )
    session.add_all((package, release, workflow))
    session.flush()
    session.add_all((package_version, workflow_version))
    session.flush()
    session.add_all((release_item, definition))
    session.flush()
    published_at = utc_now()
    package_version.status = "published"
    package_version.published_at = published_at
    release.status = "published"
    release.published_at = published_at
    release.published_by = principal_id
    session.flush()
    return RuntimeDefaults(
        content_release_id=release.id,
        workflow_definition_version_id=workflow_version.id,
    )
