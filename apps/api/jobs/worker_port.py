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


@dataclass(frozen=True, slots=True)
class VideoGenerationJobRouting:
    organization_id: UUID
    project_id: UUID
    lesson_unit_id: UUID
    node_run_id: UUID
    created_by: UUID
    creation_prompt_version_id: UUID
    creation_batch_id: UUID
    creation_request: dict[str, object]
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
                    (
                        "lesson_plan.generate",
                        "lesson.division.generate",
                        "intro.generate_options",
                    )
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

    def get_video_golden_slice(self, job_id: UUID) -> VideoGenerationJobRouting | None:
        row = self._session.execute(
            select(
                GenerationJob.organization_id,
                GenerationJob.project_id,
                GenerationJob.lesson_unit_id,
                GenerationJob.node_run_id,
                GenerationJob.created_by,
                GenerationJob.creation_prompt_version_id,
                GenerationJob.creation_batch_id,
                GenerationJob.creation_request_json,
                GenerationJob.status,
            ).where(
                GenerationJob.id == job_id,
                GenerationJob.job_type == "video.golden_slice",
                GenerationJob.workflow_node_key == "video.shots.generate",
                GenerationJob.project_id.is_not(None),
                GenerationJob.lesson_unit_id.is_not(None),
                GenerationJob.node_run_id.is_not(None),
                GenerationJob.creation_prompt_version_id.is_not(None),
                GenerationJob.creation_batch_id.is_not(None),
                GenerationJob.creation_request_json.is_not(None),
                GenerationJob.deleted_at.is_(None),
            )
        ).one_or_none()
        if (
            row is None
            or row.project_id is None
            or row.lesson_unit_id is None
            or row.node_run_id is None
            or row.creation_prompt_version_id is None
            or row.creation_batch_id is None
            or row.creation_request_json is None
        ):
            return None
        return VideoGenerationJobRouting(
            organization_id=row.organization_id,
            project_id=row.project_id,
            lesson_unit_id=row.lesson_unit_id,
            node_run_id=row.node_run_id,
            created_by=row.created_by,
            creation_prompt_version_id=row.creation_prompt_version_id,
            creation_batch_id=row.creation_batch_id,
            creation_request=dict(row.creation_request_json),
            status=row.status,
        )

    def video_cancel_requested(self, job_id: UUID) -> bool:
        status = self._session.scalar(
            select(GenerationJob.status).where(
                GenerationJob.id == job_id,
                GenerationJob.job_type == "video.golden_slice",
                GenerationJob.deleted_at.is_(None),
            )
        )
        return status in {"cancel_requested", "cancelled"}
