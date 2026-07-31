from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from apps.api.database import build_engine, build_session_factory
from apps.api.identity.models import Organization, OrganizationMember, Principal, User


def test_production_identity_bootstrap_is_idempotent_on_postgresql(
    migrated_database_url: str,
) -> None:
    from apps.api.identity.production_bootstrap import bootstrap_production_identity

    principal_id = UUID("01960000-0000-7000-8000-000000000002")
    engine = build_engine(migrated_database_url)
    factory = build_session_factory(engine)
    try:
        with factory() as session, session.begin():
            first = bootstrap_production_identity(session, principal_id=principal_id)
        with factory() as session, session.begin():
            second = bootstrap_production_identity(session, principal_id=principal_id)
        with factory() as session:
            principal = session.get(Principal, principal_id)
            assert principal is not None
            assert principal.organization_id == first.organization_id
            assert session.scalar(select(func.count()).select_from(User)) == 1
            assert session.scalar(select(func.count()).select_from(Organization)) == 2
            assert session.scalar(select(func.count()).select_from(OrganizationMember)) == 1
    finally:
        engine.dispose()

    assert first.created is True
    assert second.created is False
    assert second == first.__class__(
        created=False,
        organization_id=first.organization_id,
        user_id=first.user_id,
        principal_id=first.principal_id,
    )
