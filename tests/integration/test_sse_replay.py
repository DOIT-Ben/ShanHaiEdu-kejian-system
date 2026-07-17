from __future__ import annotations

import pytest
from sqlalchemy import delete

from apps.api.database import build_engine, build_session_factory
from apps.api.errors import ApiError
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID
from apps.api.projects.repository import ProjectRepository
from apps.api.projects.schemas import CreateProjectRequest
from apps.api.reliability.events import EventResource, EventWriter
from apps.api.reliability.models import EventStreamEntry
from apps.api.reliability.sse import EventReplayRepository, encode_sse
from tests.fakes.identity import seed_test_actor


def test_sse_replays_after_last_event_id_and_detects_expired_history(
    migrated_database_url: str,
) -> None:
    factory = build_session_factory(build_engine(migrated_database_url))
    with factory() as session, session.begin():
        actor = seed_test_actor(session)
        project = ProjectRepository(session, actor).create(
            CreateProjectRequest(title="Fractions", knowledge_point="One half")
        )
        writer = EventWriter(session, SYSTEM_ORGANIZATION_ID)
        for progress in (0, 50, 100):
            writer.append(
                project_id=project.id,
                event_type="generation.job.progress",
                resource=EventResource(type="project", id=project.id),
                payload={"progress_percent": progress},
                request_id=f"req-progress-{progress}",
            )
        project_id = project.id

    with factory() as session:
        replay = EventReplayRepository(session, SYSTEM_ORGANIZATION_ID).replay(
            project_id=project_id,
            after_sequence=1,
        )
        assert [event.sequence_no for event in replay] == [2, 3]
        encoded = encode_sse(replay[0])
        assert encoded.startswith("id: 2\nevent: generation.job.progress\n")
        assert '"sequence_no":2' in encoded

    with factory() as session, session.begin():
        session.execute(
            delete(EventStreamEntry).where(
                EventStreamEntry.project_id == project_id,
                EventStreamEntry.sequence_no <= 2,
            )
        )

    with factory() as session, pytest.raises(ApiError, match="EVENT_HISTORY_EXPIRED"):
        EventReplayRepository(session, SYSTEM_ORGANIZATION_ID).replay(
            project_id=project_id,
            after_sequence=1,
        )
