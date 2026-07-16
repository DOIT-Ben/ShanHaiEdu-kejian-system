from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from apps.api.database import build_engine, build_session_factory
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID
from apps.api.projects.models import Project
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest


def test_project_repository_enforces_tenant_and_rolls_back_unique_failure(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    request = CreateProjectRequest(title="Fractions", knowledge_point="Understanding one half")
    with factory() as session:
        with session.begin():
            first = ProjectRepository(session, SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID).create(
                request
            )
        first_id = first.id
        project_no = first.project_no

        with pytest.raises(IntegrityError):
            with session.begin():
                duplicate = ProjectRepository(
                    session, SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID
                ).create(request)
                duplicate.project_no = project_no
                session.flush()

        assert session.scalar(select(func.count()).select_from(Project)) == 1
        assert (
            ProjectRepository(session, SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID).get(first_id)
            is not None
        )
        assert ProjectRepository(session, uuid4(), SYSTEM_PRINCIPAL_ID).get(first_id) is None

        session.rollback()
        with pytest.raises(IntegrityError):
            with session.begin():
                persisted = session.get(Project, first_id)
                assert persisted is not None
                persisted.created_by = uuid4()
                session.flush()
