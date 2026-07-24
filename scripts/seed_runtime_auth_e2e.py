#!/usr/bin/env python3
"""Seed a random CI-only teacher for the real API authentication browser gate."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from apps.api.database import build_engine, build_session_factory
from apps.api.identity.models import Organization, OrganizationMember, Principal, User


def required_uuid(name: str) -> UUID:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return UUID(value)


def main() -> int:
    database_url = os.environ.get("SHANHAI_DATABASE_URL")
    if not database_url:
        raise RuntimeError("SHANHAI_DATABASE_URL is required")
    user_id = required_uuid("SHANHAI_E2E_TEACHER_USER_ID")
    principal_id = required_uuid("SHANHAI_SESSION_TEACHER_PRINCIPAL_ID")
    member_id = required_uuid("SHANHAI_E2E_TEACHER_MEMBER_ID")
    engine = build_engine(database_url)
    factory = build_session_factory(engine)
    try:
        with factory() as database, database.begin():
            organization = database.scalar(
                select(Organization)
                .where(Organization.status == "active")
                .order_by(Organization.id)
                .limit(1)
            )
            if organization is None:
                raise RuntimeError("an active organization is required")
            now = datetime.now(UTC)
            user = User(
                id=user_id,
                email=f"runtime-auth-{user_id.hex}@example.test",
                display_name="R1 Teacher",
                status="active",
                created_at=now,
            )
            database.add(user)
            database.flush()
            database.add_all(
                (
                    OrganizationMember(
                        id=member_id,
                        organization_id=organization.id,
                        user_id=user.id,
                        role="member",
                        status="active",
                        created_at=now,
                    ),
                    Principal(
                        id=principal_id,
                        organization_id=organization.id,
                        user_id=user.id,
                        principal_type="user",
                        display_name=user.display_name,
                        status="active",
                        created_at=now,
                    ),
                )
            )
        print("runtime authentication teacher seeded")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
