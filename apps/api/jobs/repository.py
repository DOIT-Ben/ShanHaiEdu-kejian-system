"""Tenant-scoped generation job repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.jobs.models import GenerationJob


class GenerationJobRepository:
    def __init__(self, session: Session, organization_id: UUID) -> None:
        self._session = session
        self._organization_id = organization_id

    def get(self, job_id: UUID, *, for_update: bool = False) -> GenerationJob | None:
        statement = select(GenerationJob).where(
            GenerationJob.id == job_id,
            GenerationJob.organization_id == self._organization_id,
            GenerationJob.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)
