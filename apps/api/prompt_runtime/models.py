"""Immutable context and prompt snapshot persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, utc_now


class ContextSnapshot(Base):
    __tablename__ = "context_snapshots"
    __table_args__ = (
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_format"),
        Index("uq_context_snapshots_node_run", "node_run_id", unique=True),
        Index(
            "ix_context_snapshots_organization_project_created",
            "organization_id",
            "project_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    node_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("node_runs.id", ondelete="RESTRICT"), nullable=False
    )
    bindings_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )


class PromptSnapshot(Base):
    __tablename__ = "prompt_snapshots"
    __table_args__ = (
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_format"),
        Index("uq_prompt_snapshots_node_run", "node_run_id", unique=True),
        Index("uq_prompt_snapshots_context", "context_snapshot_id", unique=True),
        Index(
            "ix_prompt_snapshots_organization_project_created",
            "organization_id",
            "project_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    node_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("node_runs.id", ondelete="RESTRICT"), nullable=False
    )
    context_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("context_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    template_refs_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    layers_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    editable_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_diff_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    compiled_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    request_schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    preview_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("principals.id", ondelete="RESTRICT"), nullable=False
    )
