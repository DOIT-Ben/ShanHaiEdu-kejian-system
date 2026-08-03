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

    def active_for_node(
        self,
        node_run_id: UUID,
        *,
        for_update: bool = False,
    ) -> GenerationJob | None:
        statement = select(GenerationJob).where(
            GenerationJob.organization_id == self._organization_id,
            GenerationJob.node_run_id == node_run_id,
            GenerationJob.status.in_(("created", "queued", "running", "cancel_requested")),
            GenerationJob.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def active_material_parse(
        self,
        source_material_id: UUID,
        *,
        for_update: bool = False,
    ) -> GenerationJob | None:
        statement = select(GenerationJob).where(
            GenerationJob.organization_id == self._organization_id,
            GenerationJob.source_material_id == source_material_id,
            GenerationJob.job_type == "material.parse",
            GenerationJob.status.in_(("created", "queued", "running", "cancel_requested")),
            GenerationJob.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def list_lesson_plan_jobs(
        self,
        project_id: UUID,
        lesson_unit_id: UUID,
        *,
        limit: int = 100,
    ) -> list[GenerationJob]:
        return list(
            self._session.scalars(
                select(GenerationJob)
                .where(
                    GenerationJob.organization_id == self._organization_id,
                    GenerationJob.project_id == project_id,
                    GenerationJob.lesson_unit_id == lesson_unit_id,
                    GenerationJob.workflow_node_key == "lesson_plan.generate",
                    GenerationJob.deleted_at.is_(None),
                )
                .order_by(GenerationJob.id.desc())
                .limit(limit)
            )
        )

    def list_intro_option_jobs(
        self,
        project_id: UUID,
        lesson_unit_id: UUID,
        *,
        limit: int = 100,
    ) -> list[GenerationJob]:
        return list(
            self._session.scalars(
                select(GenerationJob)
                .where(
                    GenerationJob.organization_id == self._organization_id,
                    GenerationJob.project_id == project_id,
                    GenerationJob.lesson_unit_id == lesson_unit_id,
                    GenerationJob.workflow_node_key == "intro.generate_options",
                    GenerationJob.deleted_at.is_(None),
                )
                .order_by(GenerationJob.id.desc())
                .limit(limit)
            )
        )

    def list_lesson_division_jobs(
        self,
        project_id: UUID,
        *,
        limit: int = 100,
    ) -> list[GenerationJob]:
        return list(
            self._session.scalars(
                select(GenerationJob)
                .where(
                    GenerationJob.organization_id == self._organization_id,
                    GenerationJob.project_id == project_id,
                    GenerationJob.lesson_unit_id.is_(None),
                    GenerationJob.workflow_node_key == "lesson.division.generate",
                    GenerationJob.deleted_at.is_(None),
                )
                .order_by(GenerationJob.id.desc())
                .limit(limit)
            )
        )
