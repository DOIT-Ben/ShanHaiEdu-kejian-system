"""Lease-based transactional outbox dispatch."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.database import utc_now
from apps.api.reliability.models import OutboxEvent

PublishEvent = Callable[[OutboxEvent], None]


class OutboxDispatcher:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        worker_id: str,
        lease_seconds: int,
        retry_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._retry_seconds = retry_seconds

    def dispatch_batch(self, publish: PublishEvent, *, limit: int = 50) -> int:
        event_ids = self._claim(limit)
        published = 0
        for event_id in event_ids:
            try:
                with self._session_factory() as session:
                    event = session.get(OutboxEvent, event_id)
                    if event is None:
                        continue
                    publish(event)
                self._mark_published(event_id)
                published += 1
            except Exception as exc:
                self._mark_retry(event_id, type(exc).__name__)
        return published

    def _claim(self, limit: int) -> list[UUID]:
        now = utc_now()
        with self._session_factory() as session, session.begin():
            events = list(
                session.scalars(
                    select(OutboxEvent)
                    .where(
                        OutboxEvent.available_at <= now,
                        (
                            (OutboxEvent.status == "pending")
                            | (
                                (OutboxEvent.status == "publishing")
                                & (OutboxEvent.lease_expires_at < now)
                            )
                        ),
                    )
                    .order_by(OutboxEvent.created_at, OutboxEvent.event_id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            for event in events:
                event.status = "publishing"
                event.lease_owner = self._worker_id
                event.lease_expires_at = now + timedelta(seconds=self._lease_seconds)
                event.attempt_count += 1
            return [event.event_id for event in events]

    def _mark_published(self, event_id: UUID) -> None:
        with self._session_factory() as session, session.begin():
            event = session.get(OutboxEvent, event_id, with_for_update=True)
            if event is None or event.lease_owner != self._worker_id:
                return
            event.status = "published"
            event.published_at = utc_now()
            event.lease_owner = None
            event.lease_expires_at = None
            event.last_error = None

    def _mark_retry(self, event_id: UUID, error_type: str) -> None:
        with self._session_factory() as session, session.begin():
            event = session.get(OutboxEvent, event_id, with_for_update=True)
            if event is None or event.lease_owner != self._worker_id:
                return
            event.status = "pending"
            event.available_at = utc_now() + timedelta(seconds=self._retry_seconds)
            event.lease_owner = None
            event.lease_expires_at = None
            event.last_error = error_type[:200]
