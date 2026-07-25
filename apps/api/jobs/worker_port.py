"""Worker-only immutable routing facts for exact generation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.jobs.models import GenerationJob


@dataclass(frozen=True, slots=True)
class GenerationJobRouting:
    organization_id: UUID
    node_run_id: UUID
    created_by: UUID
    creation_request: dict[str, object] | None
    status: str


class GenerationJobRoutingReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_supported_r1(self, job_id: UUID) -> GenerationJobRouting | None:
        row = self._session.execute(
            select(
                GenerationJob.organization_id,
                GenerationJob.node_run_id,
                GenerationJob.created_by,
                GenerationJob.creation_request_json,
                GenerationJob.status,
            ).where(
                GenerationJob.id == job_id,
                GenerationJob.job_type == "workflow.node",
                GenerationJob.workflow_node_key.in_(
                    ("lesson_plan.generate", "lesson.division.generate")
                ),
                GenerationJob.node_run_id.is_not(None),
                GenerationJob.deleted_at.is_(None),
            )
        ).one_or_none()
        if row is None or row.node_run_id is None:
            return None
        return GenerationJobRouting(
            organization_id=row.organization_id,
            node_run_id=row.node_run_id,
            created_by=row.created_by,
            creation_request=row.creation_request_json,
            status=row.status,
        )
