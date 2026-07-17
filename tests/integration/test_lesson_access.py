from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from apps.api.database import build_session_factory
from apps.api.identity.context import ActorContext, AuthenticatedIdentity
from apps.api.identity.dependencies import get_authenticated_identity
from apps.api.identity.models import (
    Organization,
    OrganizationMember,
    Principal,
    ProjectMember,
    User,
)
from apps.api.lessons.domain import ApprovedLessonDivision, ApprovedLessonItem
from apps.api.lessons.service import LessonService
from apps.api.main import create_app
from apps.api.settings import Settings
from tests.conftest import run_migration

ORG_A = UUID("01940000-0000-7000-8000-000000000001")
ORG_B = UUID("01940000-0000-7000-8000-000000000002")
OWNER = (UUID("01940000-0000-7000-8000-000000000011"), UUID("01940000-0000-7000-8000-000000000012"))
EDITOR = (
    UUID("01940000-0000-7000-8000-000000000021"),
    UUID("01940000-0000-7000-8000-000000000022"),
)
REVIEWER = (
    UUID("01940000-0000-7000-8000-000000000031"),
    UUID("01940000-0000-7000-8000-000000000032"),
)
VIEWER = (
    UUID("01940000-0000-7000-8000-000000000041"),
    UUID("01940000-0000-7000-8000-000000000042"),
)
NON_MEMBER = (
    UUID("01940000-0000-7000-8000-000000000051"),
    UUID("01940000-0000-7000-8000-000000000052"),
)
OUTSIDER = (
    UUID("01940000-0000-7000-8000-000000000061"),
    UUID("01940000-0000-7000-8000-000000000062"),
)


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


def add_actor(
    session: Session,
    organization_id: UUID,
    ids: tuple[UUID, UUID],
    name: str,
) -> ActorContext:
    user_id, principal_id = ids
    now = datetime.now(UTC)
    session.add(
        User(
            id=user_id,
            email=f"{name}@example.test",
            display_name=name,
            status="active",
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
    return ActorContext(
        organization_id=organization_id,
        principal_id=principal_id,
        user_id=user_id,
        actor_type="user",
        organization_role="member",
    )


def use_actor(app, actor: ActorContext) -> None:
    async def override() -> AuthenticatedIdentity:
        assert actor.user_id is not None
        return AuthenticatedIdentity(
            user_id=actor.user_id,
            organization_id=actor.organization_id,
        )

    app.dependency_overrides[get_authenticated_identity] = override


async def test_lesson_access_inherits_project_roles_and_tenant_non_disclosure(
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
    factory = build_session_factory(app.state.database_engine)
    transport = httpx.ASGITransport(app=app)
    try:
        with factory() as session, session.begin():
            add_organization(session, ORG_A, "lesson-org-a")
            add_organization(session, ORG_B, "lesson-org-b")
            owner = add_actor(session, ORG_A, OWNER, "lesson-owner")
            editor = add_actor(session, ORG_A, EDITOR, "lesson-editor")
            reviewer = add_actor(session, ORG_A, REVIEWER, "lesson-reviewer")
            viewer = add_actor(session, ORG_A, VIEWER, "lesson-viewer")
            non_member = add_actor(session, ORG_A, NON_MEMBER, "lesson-non-member")
            outsider = add_actor(session, ORG_B, OUTSIDER, "lesson-outsider")

        use_actor(app, owner)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "lesson-access-project-001"},
                json={"title": "Fractions", "knowledge_point": "One half"},
            )
            project_id = UUID(created.json()["data"]["id"])

        with factory() as session, session.begin():
            for actor, role in ((editor, "editor"), (reviewer, "reviewer"), (viewer, "viewer")):
                assert actor.user_id is not None
                session.add(
                    ProjectMember(
                        id=UUID(int=actor.user_id.int + 2),
                        project_id=project_id,
                        user_id=actor.user_id,
                        role=role,
                        created_at=datetime.now(UTC),
                    )
                )
            lesson = LessonService(session, owner).synchronize_approved_division(
                project_id,
                ApprovedLessonDivision(
                    version_id=UUID("01940000-0000-7000-8000-000000000071"),
                    lessons=(
                        ApprovedLessonItem(
                            lesson_key="lesson-01",
                            position=1,
                            title="First",
                            scope_summary="Scope",
                            objective_summary="Objective",
                            estimated_minutes=40,
                        ),
                    ),
                ),
                request_id="req_access_sync",
            )[0]

        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for actor in (owner, editor, reviewer, viewer):
                use_actor(app, actor)
                listing = await client.get(f"/api/v2/projects/{project_id}/lessons")
                detail = await client.get(f"/api/v2/lessons/{lesson.id}")
                assert listing.status_code == 200
                assert detail.status_code == 200

            use_actor(app, editor)
            editor_update = await client.patch(
                f"/api/v2/lessons/{lesson.id}/branches",
                headers={"Idempotency-Key": "lesson-editor-update-001", "If-Match": 'W/"1"'},
                json={"branches": [{"branch_key": "ppt", "enabled": True, "settings": {}}]},
            )
            assert editor_update.status_code == 200

            for index, actor in enumerate((reviewer, viewer)):
                use_actor(app, actor)
                denied = await client.patch(
                    f"/api/v2/lessons/{lesson.id}/branches",
                    headers={
                        "Idempotency-Key": f"lesson-readonly-update-{index:03d}",
                        "If-Match": 'W/"2"',
                    },
                    json={"branches": [{"branch_key": "video", "enabled": True, "settings": {}}]},
                )
                assert denied.status_code == 403
                assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

            for actor in (non_member, outsider):
                use_actor(app, actor)
                listing = await client.get(f"/api/v2/projects/{project_id}/lessons")
                detail = await client.get(f"/api/v2/lessons/{lesson.id}")
                denied = await client.patch(
                    f"/api/v2/lessons/{lesson.id}/branches",
                    headers={"Idempotency-Key": "lesson-hidden-update-001", "If-Match": 'W/"2"'},
                    json={"branches": [{"branch_key": "video", "enabled": True, "settings": {}}]},
                )
                assert listing.status_code == 404
                assert detail.status_code == 404
                assert denied.status_code == 404
    finally:
        app.state.database_engine.dispose()
