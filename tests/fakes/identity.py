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


def seed_test_actor(
    session: Session,
    *,
    organization_id: UUID = SYSTEM_ORGANIZATION_ID,
) -> ActorContext:
    now = datetime.now(UTC)
    session.add(
        User(
            id=TEST_USER_ID,
            email="test-owner@example.test",
            display_name="Test Owner",
            status="active",
            created_at=now,
        )
    )
    session.flush()
    session.add_all(
        (
            OrganizationMember(
                id=UUID("01900000-0000-7000-8000-000000000103"),
                organization_id=organization_id,
                user_id=TEST_USER_ID,
                role="member",
                status="active",
                created_at=now,
            ),
            Principal(
                id=TEST_PRINCIPAL_ID,
                organization_id=organization_id,
                user_id=TEST_USER_ID,
                principal_type="user",
                display_name="Test Owner",
                status="active",
                created_at=now,
            ),
        )
    )
    session.flush()
    return ActorContext(
        organization_id=organization_id,
        principal_id=TEST_PRINCIPAL_ID,
        user_id=TEST_USER_ID,
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
