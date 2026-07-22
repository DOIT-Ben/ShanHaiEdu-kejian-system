"""Shared transaction lock for artifact relation graph mutations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def lock_relation_graph(session: Session, organization_id: UUID) -> None:
    lock_id = int.from_bytes(organization_id.bytes[:8], byteorder="big", signed=True)
    session.execute(select(func.pg_advisory_xact_lock(lock_id)))
