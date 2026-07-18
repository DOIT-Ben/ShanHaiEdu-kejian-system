"""Generation job persistence model."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, MutableAuditMixin


class GenerationJob(MutableAuditMixin, Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created', 'queued', 'running', 'succeeded', 'failed', "
            "'cancel_requested', 'cancelled')",
            name="status_allowed",
        ),
        CheckConstraint("progress_percent BETWEEN 0 AND 100", name="progress_range"),
        CheckConstraint("priority >= 0", name="priority_nonnegative"),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        CheckConstraint(
            "project_id IS NOT NULL OR source_material_id IS NOT NULL "
            "OR creation_prompt_version_id IS NOT NULL OR creation_batch_id IS NOT NULL",
            name="stage0_source_present",
        ),
        Index(
            "ix_generation_jobs_organization_status_created",
            "organization_id",
            "status",
            "created_at",
        ),
        Index("ix_generation_jobs_status_lease", "status", "lease_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT")
    )
    source_material_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("source_materials.id", ondelete="RESTRICT")
    )
    creation_prompt_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("creation_prompt_versions.id", ondelete="RESTRICT")
    )
    creation_batch_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("creation_batches.id", ondelete="RESTRICT")
    )
    creation_request_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_message: Mapped[str | None] = mapped_column(String(500))
    error_code: Mapped[str | None] = mapped_column(String(100))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(160))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
