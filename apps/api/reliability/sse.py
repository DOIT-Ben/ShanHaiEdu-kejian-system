"""PostgreSQL-backed SSE replay and formatting."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.errors import ApiError
from apps.api.identity.models import SYSTEM_ORGANIZATION_ID
from apps.api.reliability.models import EventStreamEntry


def parse_last_event_id(value: str | None) -> int:
    if value is None:
        return 0
    try:
        cursor = int(value)
    except ValueError as exc:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="Last-Event-ID must be a positive event sequence.",
        ) from exc
    if cursor < 0:
        raise ApiError(
            status_code=422,
            code="VALIDATION_FAILED",
            message="Last-Event-ID must be a positive event sequence.",
        )
    return cursor


class EventReplayRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replay(
        self,
        *,
        project_id: UUID,
        after_sequence: int,
        resource: tuple[Literal["generation_job"], UUID] | None = None,
        limit: int = 100,
    ) -> list[EventStreamEntry]:
        self._require_cursor_available(project_id, after_sequence)
        statement = (
            select(EventStreamEntry)
            .where(
                EventStreamEntry.organization_id == SYSTEM_ORGANIZATION_ID,
                EventStreamEntry.project_id == project_id,
                EventStreamEntry.sequence_no > after_sequence,
            )
            .order_by(EventStreamEntry.sequence_no)
            .limit(limit)
        )
        if resource is not None:
            statement = statement.where(
                EventStreamEntry.resource_type == resource[0],
                EventStreamEntry.resource_id == resource[1],
            )
        return list(self._session.scalars(statement))

    def _require_cursor_available(self, project_id: UUID, after_sequence: int) -> None:
        if after_sequence == 0:
            return
        minimum = self._session.scalar(
            select(func.min(EventStreamEntry.sequence_no)).where(
                EventStreamEntry.organization_id == SYSTEM_ORGANIZATION_ID,
                EventStreamEntry.project_id == project_id,
            )
        )
        if minimum is not None and after_sequence < minimum - 1:
            raise ApiError(
                status_code=409,
                code="EVENT_HISTORY_EXPIRED",
                message="The event cursor is outside the retained history window.",
                details={"recovery": "reload_rest_snapshot"},
            )


def encode_sse(entry: EventStreamEntry) -> str:
    data = json.dumps(entry.summary_json, separators=(",", ":"), ensure_ascii=True)
    return f"id: {entry.sequence_no}\nevent: {entry.event_type}\ndata: {data}\n\n"


def encode_heartbeat() -> str:
    return ": heartbeat\n\n"


def stream_events(
    session_factory: sessionmaker[Session],
    *,
    project_id: UUID,
    after_sequence: int,
    resource: tuple[Literal["generation_job"], UUID] | None,
    poll_seconds: float,
    heartbeat_seconds: float,
) -> Iterator[str]:
    cursor = after_sequence
    last_activity = time.monotonic()
    while True:
        with session_factory() as session:
            entries = EventReplayRepository(session).replay(
                project_id=project_id,
                after_sequence=cursor,
                resource=resource,
            )
        if entries:
            for entry in entries:
                cursor = entry.sequence_no
                last_activity = time.monotonic()
                yield encode_sse(entry)
            continue
        if time.monotonic() - last_activity >= heartbeat_seconds:
            last_activity = time.monotonic()
            yield encode_heartbeat()
        time.sleep(poll_seconds)
