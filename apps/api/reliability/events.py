"""Atomic outbox and replayable event-stream writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.database import utc_now
from apps.api.ids import new_uuid7
from apps.api.projects.models import Project
from apps.api.reliability.models import EventStreamEntry, OutboxEvent


@dataclass(frozen=True, slots=True)
class EventResource:
    type: str
    id: UUID


class EventWriter:
    def __init__(self, session: Session, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    def append(
        self,
        *,
        project_id: UUID,
        event_type: str,
        resource: EventResource,
        payload: dict[str, Any],
        request_id: str | None,
    ) -> EventStreamEntry:
        project = self._session.scalar(
            select(Project)
            .where(
                Project.id == project_id,
                Project.organization_id == self._organization_id,
            )
            .with_for_update()
        )
        if project is None:
            raise ValueError("event project does not exist in the organization")
        sequence_no = (
            self._session.scalar(
                select(func.max(EventStreamEntry.sequence_no)).where(
                    EventStreamEntry.project_id == project_id
                )
            )
            or 0
        ) + 1
        event_id = new_uuid7()
        occurred_at = utc_now()
        summary = {
            "event_id": str(event_id),
            "sequence_no": sequence_no,
            "event_type": event_type,
            "occurred_at": occurred_at.isoformat(),
            "project_id": str(project_id),
            "resource": {"type": resource.type, "id": str(resource.id)},
            "payload": payload,
            "request_id": request_id,
        }
        entry = EventStreamEntry(
            event_id=event_id,
            organization_id=self._organization_id,
            project_id=project_id,
            sequence_no=sequence_no,
            event_type=event_type,
            resource_type=resource.type,
            resource_id=resource.id,
            summary_json=summary,
            request_id=request_id,
            created_at=occurred_at,
        )
        outbox = OutboxEvent(
            event_id=event_id,
            organization_id=self._organization_id,
            topic=event_type,
            aggregate_type=resource.type,
            aggregate_id=resource.id,
            payload_json=summary,
            status="pending",
            available_at=occurred_at,
            attempt_count=0,
            created_at=occurred_at,
        )
        self._session.add_all((entry, outbox))
        self._session.flush()
        return entry


def append_outbox_only(
    session: Session,
    organization_id: UUID,
    *,
    event_type: str,
    resource: EventResource,
    payload: dict[str, Any],
    request_id: str | None,
) -> OutboxEvent:
    """Write a tenant event that has no project-scoped SSE stream."""
    event_id = new_uuid7()
    occurred_at = utc_now()
    summary = {
        "event_id": str(event_id),
        "event_type": event_type,
        "occurred_at": occurred_at.isoformat(),
        "project_id": None,
        "resource": {"type": resource.type, "id": str(resource.id)},
        "payload": payload,
        "request_id": request_id,
    }
    outbox = OutboxEvent(
        event_id=event_id,
        organization_id=organization_id,
        topic=event_type,
        aggregate_type=resource.type,
        aggregate_id=resource.id,
        payload_json=summary,
        status="pending",
        available_at=occurred_at,
        attempt_count=0,
        created_at=occurred_at,
    )
    session.add(outbox)
    session.flush()
    return outbox
