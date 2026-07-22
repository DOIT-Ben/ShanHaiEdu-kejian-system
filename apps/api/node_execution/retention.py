"""Bounded retention cleanup for abandoned validated recovery facts."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.database import database_wall_clock

from .models import NodeExecutionRecoveryFact


class RecoveryFactRetentionCoordinator:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def cleanup_expired(self, *, limit: int = 100) -> int:
        if limit < 1:
            raise ValueError("recovery fact cleanup limit must be positive")
        with self._session_factory() as session, session.begin():
            expired_ids = tuple(
                session.scalars(
                    select(NodeExecutionRecoveryFact.id)
                    .where(NodeExecutionRecoveryFact.expires_at <= database_wall_clock(session))
                    .order_by(
                        NodeExecutionRecoveryFact.expires_at,
                        NodeExecutionRecoveryFact.id,
                    )
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            if not expired_ids:
                return 0
            session.execute(
                delete(NodeExecutionRecoveryFact).where(
                    NodeExecutionRecoveryFact.id.in_(expired_ids)
                )
            )
            return len(expired_ids)
