"""Project persistence model."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Uuid
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
    automation_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="assisted")
    owner_principal_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
    lesson_division_version_id: Mapped[UUID | None] = mapped_column(Uuid)
