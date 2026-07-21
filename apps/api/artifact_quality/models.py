"""Immutable artifact quality-report persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, utc_now


class ArtifactQualityReport(Base):
    __tablename__ = "artifact_quality_reports"
    __table_args__ = (
        CheckConstraint(
            "source_content_hash ~ '^[0-9a-f]{64}$'",
            name="source_content_hash_format",
        ),
        CheckConstraint(
            "validator_set_hash ~ '^[0-9a-f]{64}$'",
            name="validator_set_hash_format",
        ),
        CheckConstraint(
            "evidence_hash ~ '^[0-9a-f]{64}$'",
            name="evidence_hash_format",
        ),
        CheckConstraint(
            "conclusion IN ('passed', 'failed')",
            name="conclusion_allowed",
        ),
        CheckConstraint(
            "jsonb_typeof(validator_set_json) = 'array' "
            "AND jsonb_array_length(validator_set_json) > 0",
            name="validator_set_array",
        ),
        CheckConstraint(
            "jsonb_typeof(findings_json) = 'array'",
            name="findings_array",
        ),
        Index(
            "uq_artifact_quality_reports_source_workflow_validators",
            "source_artifact_version_id",
            "workflow_definition_version_id",
            "validator_set_hash",
            unique=True,
        ),
        Index(
            "uq_artifact_quality_reports_validate_node_run",
            "validate_node_run_id",
            unique=True,
        ),
        Index(
            "ix_artifact_quality_reports_project_source",
            "organization_id",
            "project_id",
            "source_artifact_version_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "organizations.id",
            name="fk_artifact_quality_reports_organization",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "projects.id",
            name="fk_artifact_quality_reports_project",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    lesson_unit_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "lesson_units.id",
            name="fk_artifact_quality_reports_lesson_unit",
            ondelete="RESTRICT",
        ),
    )
    source_artifact_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "artifact_versions.id",
            name="fk_artifact_quality_reports_source_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    source_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_release_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "content_releases.id",
            name="fk_artifact_quality_reports_content_release",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    workflow_definition_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workflow_definition_versions.id",
            name="fk_artifact_quality_reports_workflow_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    validate_node_run_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "node_runs.id",
            name="fk_artifact_quality_reports_validate_node_run",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    validator_set_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    validator_set_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    conclusion: Mapped[str] = mapped_column(String(20), nullable=False)
    findings_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("principals.id", ondelete="RESTRICT"),
        nullable=False,
    )
