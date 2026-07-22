"""Persistence model for immutable Intro option selections."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, utc_now


class IntroSelection(Base):
    __tablename__ = "intro_selections"
    __table_args__ = (
        CheckConstraint(
            "selection_method IN ('teacher_selected', 'policy_default')",
            name="selection_method_allowed",
        ),
        CheckConstraint(
            "actor_type IN ('user', 'system')",
            name="actor_type_allowed",
        ),
        CheckConstraint(
            "(selection_method = 'teacher_selected' AND actor_type = 'user' "
            "AND actor_user_id IS NOT NULL) OR "
            "(selection_method = 'policy_default' AND actor_type = 'system' "
            "AND actor_user_id IS NULL)",
            name="method_actor_consistent",
        ),
        CheckConstraint("length(btrim(reason)) > 0", name="reason_nonempty"),
        CheckConstraint(
            "(active AND deactivated_at IS NULL AND deactivated_by IS NULL) OR "
            "(NOT active AND deactivated_at IS NOT NULL AND deactivated_by IS NOT NULL)",
            name="active_deactivation_consistent",
        ),
        Index(
            "uq_intro_selections_lesson_active",
            "organization_id",
            "lesson_unit_id",
            unique=True,
            postgresql_where="active",
        ),
        Index(
            "ix_intro_selections_project_lesson_selected",
            "organization_id",
            "project_id",
            "lesson_unit_id",
            "selected_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    lesson_unit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("lesson_units.id", ondelete="RESTRICT"), nullable=False
    )
    artifact_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("artifact_versions.id", ondelete="RESTRICT"), nullable=False
    )
    source_approval_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("approvals.id", ondelete="RESTRICT"), nullable=False
    )
    selection_method: Mapped[str] = mapped_column(String(30), nullable=False)
    option_key: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT")
    )
    policy_evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    recommendation_evidence_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    selected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_by: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT")
    )
