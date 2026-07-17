from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from apps.api.content_runtime.registry import BUILTIN_RUNTIME_DEFAULTS
from apps.api.database import build_session_factory
from apps.api.identity.context import AuthenticatedIdentity, system_actor
from apps.api.identity.dependencies import get_authenticated_identity
from apps.api.identity.models import (
    SYSTEM_PRINCIPAL_ID,
    Organization,
    OrganizationMember,
    Principal,
    ProjectMember,
    User,
)
from apps.api.jobs.models import GenerationJob
from apps.api.jobs.service import GenerationJobService
from apps.api.main import create_app
from apps.api.projects.models import Project
from apps.api.settings import Settings
from tests.conftest import run_migration
from tests.fakes.object_storage import FakeObjectStorage

ORG_A = UUID("01910000-0000-7000-8000-000000000001")
ORG_B = UUID("01910000-0000-7000-8000-000000000002")
OWNER_USER = UUID("01910000-0000-7000-8000-000000000011")
OWNER_PRINCIPAL = UUID("01910000-0000-7000-8000-000000000012")
EDITOR_USER = UUID("01910000-0000-7000-8000-000000000021")
EDITOR_PRINCIPAL = UUID("01910000-0000-7000-8000-000000000022")
REVIEWER_USER = UUID("01910000-0000-7000-8000-000000000031")
REVIEWER_PRINCIPAL = UUID("01910000-0000-7000-8000-000000000032")
VIEWER_USER = UUID("01910000-0000-7000-8000-000000000041")
VIEWER_PRINCIPAL = UUID("01910000-0000-7000-8000-000000000042")
OUTSIDER_USER = UUID("01910000-0000-7000-8000-000000000051")
OUTSIDER_PRINCIPAL = UUID("01910000-0000-7000-8000-000000000052")
DISABLED_USER = UUID("01910000-0000-7000-8000-000000000061")
DISABLED_PRINCIPAL = UUID("01910000-0000-7000-8000-000000000062")


def add_organization(session: Session, organization_id: UUID, slug: str) -> None:
    session.add(
        Organization(
            id=organization_id,
            slug=slug,
            name=slug,
            status="active",
            created_at=datetime.now(UTC),
        )
    )


def add_user_actor(
    session: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    principal_id: UUID,
    name: str,
    user_status: str = "active",
) -> None:
    now = datetime.now(UTC)
    session.add(
        User(
            id=user_id,
            email=f"{name}@example.test",
            display_name=name,
            status=user_status,
            created_at=now,
        )
    )
    session.flush()
    session.add_all(
        (
            OrganizationMember(
                id=UUID(int=user_id.int + 1),
                organization_id=organization_id,
                user_id=user_id,
                role="member",
                status="active",
                created_at=now,
            ),
            Principal(
                id=principal_id,
                organization_id=organization_id,
                user_id=user_id,
                principal_type="user",
                display_name=name,
                status="active",
                created_at=now,
            ),
        )
    )


def use_identity(app: object, *, user_id: UUID, organization_id: UUID) -> None:
    async def override() -> AuthenticatedIdentity:
        return AuthenticatedIdentity(user_id=user_id, organization_id=organization_id)

    app.dependency_overrides[get_authenticated_identity] = override  # type: ignore[attr-defined]


async def client_for(app: object) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def create_project(client: httpx.AsyncClient, key: str = "identity-project-001") -> UUID:
    response = await client.post(
        "/api/v2/projects",
        headers={"Idempotency-Key": key},
        json={"title": "Fractions", "knowledge_point": "One half"},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["data"]["id"])


async def test_project_owner_membership_and_cross_tenant_non_disclosure(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    app = create_app(
        settings=Settings(_env_file=None, environment="test", database_url=postgres_database_url),
        object_storage=FakeObjectStorage(),
    )
    factory = build_session_factory(app.state.database_engine)
    try:
        with factory() as session, session.begin():
            add_organization(session, ORG_A, "org-a")
            add_organization(session, ORG_B, "org-b")
            add_user_actor(
                session,
                organization_id=ORG_A,
                user_id=OWNER_USER,
                principal_id=OWNER_PRINCIPAL,
                name="owner",
            )
            add_user_actor(
                session,
                organization_id=ORG_B,
                user_id=OUTSIDER_USER,
                principal_id=OUTSIDER_PRINCIPAL,
                name="outsider",
            )

        use_identity(app, user_id=OWNER_USER, organization_id=ORG_A)
        async for client in client_for(app):
            project_id = await create_project(client)

        with factory() as session:
            project = session.get(Project, project_id)
            member = session.query(ProjectMember).filter_by(project_id=project_id).one()
            assert project is not None
            assert project.organization_id == ORG_A
            assert project.owner_principal_id == OWNER_PRINCIPAL
            assert project.created_by == OWNER_PRINCIPAL
            assert member.user_id == OWNER_USER
            assert member.role == "owner"

        use_identity(app, user_id=OUTSIDER_USER, organization_id=ORG_B)
        async for client in client_for(app):
            detail = await client.get(f"/api/v2/projects/{project_id}")
            listing = await client.get("/api/v2/projects")
        assert detail.status_code == 404
        assert detail.json()["error"]["code"] == "PROJECT_NOT_FOUND"
        assert listing.status_code == 200
        assert listing.json()["data"]["items"] == []
    finally:
        app.state.database_engine.dispose()


async def test_project_roles_control_read_and_upload_generation(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    storage = FakeObjectStorage()
    app = create_app(
        settings=Settings(_env_file=None, environment="test", database_url=postgres_database_url),
        object_storage=storage,
    )
    factory = build_session_factory(app.state.database_engine)
    try:
        actors = (
            (OWNER_USER, OWNER_PRINCIPAL, "owner"),
            (EDITOR_USER, EDITOR_PRINCIPAL, "editor"),
            (REVIEWER_USER, REVIEWER_PRINCIPAL, "reviewer"),
            (VIEWER_USER, VIEWER_PRINCIPAL, "viewer"),
        )
        with factory() as session, session.begin():
            add_organization(session, ORG_A, "roles-org")
            for user_id, principal_id, role in actors:
                add_user_actor(
                    session,
                    organization_id=ORG_A,
                    user_id=user_id,
                    principal_id=principal_id,
                    name=role,
                )

        use_identity(app, user_id=OWNER_USER, organization_id=ORG_A)
        async for client in client_for(app):
            project_id = await create_project(client, "role-project-001")

        with factory() as session, session.begin():
            for user_id, _, role in actors[1:]:
                session.add(
                    ProjectMember(
                        id=UUID(int=user_id.int + 2),
                        project_id=project_id,
                        user_id=user_id,
                        role=role,
                        created_at=datetime.now(UTC),
                    )
                )

        for index, (user_id, _, role) in enumerate(actors):
            use_identity(app, user_id=user_id, organization_id=ORG_A)
            async for client in client_for(app):
                detail = await client.get(f"/api/v2/projects/{project_id}")
                upload = await client.post(
                    f"/api/v2/projects/{project_id}/materials/uploads",
                    headers={"Idempotency-Key": f"role-upload-{index:03d}"},
                    json={
                        "filename": f"{role}.pdf",
                        "media_type": "application/pdf",
                        "size_bytes": 4,
                        "sha256": "a" * 64,
                    },
                )
            assert detail.status_code == 200
            assert upload.status_code == (201 if role in {"owner", "editor"} else 403)
            if role in {"reviewer", "viewer"}:
                assert upload.json()["error"]["code"] == "PERMISSION_DENIED"

        with factory() as session, session.begin():
            job = GenerationJob(
                id=UUID("01910000-0000-7000-8000-000000000081"),
                organization_id=ORG_A,
                project_id=project_id,
                job_type="material.parse",
                status="queued",
                progress_percent=0,
                priority=100,
                created_by=OWNER_PRINCIPAL,
                updated_by=OWNER_PRINCIPAL,
            )
            session.add(job)

        use_identity(app, user_id=OWNER_USER, organization_id=ORG_A)
        async for client in client_for(app):
            owner_cancel = await client.post(
                f"/api/v2/generation-jobs/{job.id}/cancel",
                headers={"Idempotency-Key": "shared-cancel-key"},
            )
        assert owner_cancel.status_code == 202

        use_identity(app, user_id=REVIEWER_USER, organization_id=ORG_A)
        async for client in client_for(app):
            reviewer_replay = await client.post(
                f"/api/v2/generation-jobs/{job.id}/cancel",
                headers={"Idempotency-Key": "shared-cancel-key"},
            )
        assert reviewer_replay.status_code == 403
        assert reviewer_replay.json()["error"]["code"] == "PERMISSION_DENIED"
    finally:
        app.state.database_engine.dispose()


async def test_disabled_user_is_rejected_after_test_dependency_override(
    postgres_database_url: str,
) -> None:
    run_migration(postgres_database_url, "head")
    app = create_app(
        settings=Settings(_env_file=None, environment="test", database_url=postgres_database_url)
    )
    factory = build_session_factory(app.state.database_engine)
    try:
        with factory() as session, session.begin():
            add_organization(session, ORG_A, "disabled-org")
            add_user_actor(
                session,
                organization_id=ORG_A,
                user_id=DISABLED_USER,
                principal_id=DISABLED_PRINCIPAL,
                name="disabled",
                user_status="disabled",
            )
        use_identity(app, user_id=DISABLED_USER, organization_id=ORG_A)
        async for client in client_for(app):
            response = await client.get("/api/v2/projects")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"
    finally:
        app.state.database_engine.dispose()


def test_worker_uses_system_principal_with_tenant_scoped_job(
    migrated_database_url: str,
) -> None:
    app = create_app(
        settings=Settings(_env_file=None, environment="test", database_url=migrated_database_url)
    )
    factory = build_session_factory(app.state.database_engine)
    try:
        with factory() as session, session.begin():
            add_organization(session, ORG_A, "worker-org")
            add_user_actor(
                session,
                organization_id=ORG_A,
                user_id=OWNER_USER,
                principal_id=OWNER_PRINCIPAL,
                name="worker-owner",
            )
            project = Project(
                id=UUID("01910000-0000-7000-8000-000000000071"),
                organization_id=ORG_A,
                project_no="PRJ-WORKER",
                title="Worker project",
                subject="primary_math",
                school_stage="primary",
                knowledge_point="One half",
                default_language="zh-CN",
                status="draft",
                automation_mode="assisted",
                owner_principal_id=OWNER_PRINCIPAL,
                content_release_id=BUILTIN_RUNTIME_DEFAULTS.content_release_id,
                workflow_definition_version_id=(
                    BUILTIN_RUNTIME_DEFAULTS.workflow_definition_version_id
                ),
                created_by=OWNER_PRINCIPAL,
                updated_by=OWNER_PRINCIPAL,
            )
            session.add(project)
            session.flush()
            job = GenerationJob(
                id=UUID("01910000-0000-7000-8000-000000000072"),
                organization_id=ORG_A,
                project_id=project.id,
                job_type="material.parse",
                status="queued",
                progress_percent=0,
                priority=100,
                created_by=OWNER_PRINCIPAL,
                updated_by=OWNER_PRINCIPAL,
            )
            session.add(job)
            session.flush()
            job_id = job.id

        with factory() as session, session.begin():
            claimed = GenerationJobService(
                session,
                actor=system_actor(ORG_A),
                idempotency_ttl_seconds=900,
            ).claim(job_id, worker_id="identity-worker", lease_seconds=30)
            assert claimed is not None
            assert claimed.organization_id == ORG_A
            assert claimed.updated_by == SYSTEM_PRINCIPAL_ID
    finally:
        app.state.database_engine.dispose()
