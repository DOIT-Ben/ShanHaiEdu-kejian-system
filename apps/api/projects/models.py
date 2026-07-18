"""Project persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, MutableAuditMixin


class Project(MutableAuditMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("subject = 'primary_math'", name="subject_primary_math"),
        CheckConstraint("status IN ('draft', 'active', 'archived')", name="status_allowed"),
        CheckConstraint(
            "automation_mode IN ('manual', 'assisted', 'automatic')",
            name="automation_mode_allowed",
        ),
        CheckConstraint("lock_version >= 1", name="lock_version_positive"),
        Index(
            "uq_projects_organization_project_no_active",
            "organization_id",
            "project_no",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        Index("ix_projects_organization_created", "organization_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_no: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(40), nullable=False, default="primary_math")
    school_stage: Mapped[str] = mapped_column(String(40), nullable=False, default="primary")
    grade: Mapped[str | None] = mapped_column(String(40))
    textbook_edition: Mapped[str | None] = mapped_column(String(120))
    knowledge_point: Mapped[str] = mapped_column(String(255), nullable=False)
    default_language: Mapped[str] = mapped_column(String(20), nullable=False, default="zh-CN")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    legacy_automation_mode: Mapped[str] = mapped_column(
        "automation_mode",
        String(20),
        nullable=False,
        default="assisted",
    )
    owner_principal_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
    content_release_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("content_releases.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_definition_version_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "workflow_definition_versions.id",
            name="fk_projects_workflow_definition_version",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    lesson_division_version_id: Mapped[UUID | None] = mapped_column(Uuid)


class AutomationPolicy(Base):
    __tablename__ = "project_automation_policies"
    __table_args__ = (
        CheckConstraint("mode IN ('guided', 'automatic')", name="mode_allowed"),
        CheckConstraint("policy_version > 0", name="policy_version_positive"),
        Index(
            "uq_project_automation_policies_project_version",
            "project_id",
            "policy_version",
            unique=True,
        ),
        Index(
            "ix_project_automation_policies_organization_project",
            "organization_id",
            "project_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_definition_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("workflow_definition_versions.id", ondelete="RESTRICT"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    node_rules_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
