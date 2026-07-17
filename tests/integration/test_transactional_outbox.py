from __future__ import annotations

import pytest
from sqlalchemy import func, select

from apps.api.database import build_engine, build_session_factory
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID
from apps.api.projects.models import Project
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.models import EventStreamEntry, OutboxEvent
from apps.api.reliability.outbox import OutboxDispatcher


def create_project_with_event(session, title: str) -> Project:
    project = ProjectRepository(session, SYSTEM_ORGANIZATION_ID, SYSTEM_PRINCIPAL_ID).create(
        CreateProjectRequest(title=title, knowledge_point="Understanding one half")
    )
    EventWriter(session, SYSTEM_ORGANIZATION_ID).append(
        project_id=project.id,
        event_type="project.created",
        resource=EventResource(type="project", id=project.id),
        payload={"status": "draft"},
        request_id="req-outbox-test",
    )
    return project


def test_business_write_and_outbox_commit_or_rollback_together(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session:
        with pytest.raises(RuntimeError, match="rollback"):
            with session.begin():
                create_project_with_event(session, "Rolled back project")
                raise RuntimeError("rollback")

        assert session.scalar(select(func.count()).select_from(Project)) == 0
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 0
        session.rollback()

        with session.begin():
            create_project_with_event(session, "Committed project")

        assert session.scalar(select(func.count()).select_from(Project)) == 1
        assert session.scalar(select(func.count()).select_from(EventStreamEntry)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 1


def test_outbox_publish_failure_is_retried_without_losing_event(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        create_project_with_event(session, "Retry project")

    dispatcher = OutboxDispatcher(
        factory,
        worker_id="dispatcher-test",
        lease_seconds=10,
        retry_seconds=1,
    )

    def fail_publish(_event: OutboxEvent) -> None:
        raise ConnectionError("transport unavailable")

    assert dispatcher.dispatch_batch(fail_publish) == 0
    with factory() as session:
        event = session.scalar(select(OutboxEvent))
        assert event is not None
        assert event.status == "pending"
        assert event.attempt_count == 1
        assert event.last_error == "ConnectionError"
        assert event.published_at is None
