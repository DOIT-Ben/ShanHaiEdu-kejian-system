"""Deterministic identity setup used only through tests and dependency overrides."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy.orm import Session

from apps.api.database import build_session_factory
from apps.api.identity.context import ActorContext, AuthenticatedIdentity
from apps.api.identity.dependencies import get_authenticated_identity
from apps.api.identity.models import (
    SYSTEM_ORGANIZATION_ID,
    OrganizationMember,
    Principal,
    User,
)

TEST_USER_ID = UUID("01900000-0000-7000-8000-000000000101")
TEST_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000102")
TEST_MEMBER_ID = UUID("01900000-0000-7000-8000-000000000103")


def seed_test_actor(
    session: Session,
    *,
    organization_id: UUID = SYSTEM_ORGANIZATION_ID,
    user_id: UUID = TEST_USER_ID,
    principal_id: UUID = TEST_PRINCIPAL_ID,
    member_id: UUID = TEST_MEMBER_ID,
    email: str = "test-owner@example.test",
    display_name: str = "Test Owner",
) -> ActorContext:
    now = datetime.now(UTC)
    session.add(
        User(
            id=user_id,
            email=email,
            display_name=display_name,
            status="active",
            created_at=now,
        )
    )
    session.flush()
    session.add_all(
        (
            OrganizationMember(
                id=member_id,
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
                display_name=display_name,
                status="active",
                created_at=now,
            ),
        )
    )
    session.flush()
    return ActorContext(
        organization_id=organization_id,
        principal_id=principal_id,
        user_id=user_id,
        actor_type="user",
        organization_role="member",
    )


def override_test_identity(app: FastAPI, actor: ActorContext) -> None:
    if actor.user_id is None:
        raise ValueError("test HTTP identity requires a user actor")

    async def override() -> AuthenticatedIdentity:
        return AuthenticatedIdentity(
            user_id=actor.user_id,
            organization_id=actor.organization_id,
        )

    app.dependency_overrides[get_authenticated_identity] = override


def configure_test_identity(app: FastAPI) -> ActorContext:
    factory = build_session_factory(app.state.database_engine)
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
    override_test_identity(app, actor)
    return actor
