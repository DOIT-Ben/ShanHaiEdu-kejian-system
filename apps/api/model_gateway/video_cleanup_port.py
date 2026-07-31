"""Model-attempt facts used to authorize video object cleanup."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.model_gateway.audit_models import GenerationAttempt


class VideoCleanupAttemptPort:
    def __init__(self, session: Session) -> None:
        self._session = session

    def active_exists(self, job_id: UUID, organization_id: UUID, *, now: datetime) -> bool:
        return (
            self._session.scalar(
                select(GenerationAttempt.id)
                .where(
                    GenerationAttempt.generation_job_id == job_id,
                    GenerationAttempt.organization_id == organization_id,
                    GenerationAttempt.status == "running",
                    GenerationAttempt.lease_expires_at > now,
                )
                .limit(1)
            )
            is not None
        )
