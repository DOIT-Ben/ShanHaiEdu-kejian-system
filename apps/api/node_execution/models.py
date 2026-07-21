"""Private, tenant-scoped facts used to recover a validated node result."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, utc_now


class NodeExecutionRecoveryFact(Base):
    """Validated output held between audit checkpoint and artifact T2."""

    __tablename__ = "node_execution_recovery_facts"
    __table_args__ = (
        Index(
            "uq_node_execution_recovery_fact_attempt",
            "organization_id",
            "node_run_id",
            "attempt_id",
            unique=True,
        ),
        Index(
            "ix_node_execution_recovery_fact_expiry",
            "organization_id",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=False
    )
    node_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("node_runs.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("generation_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_token: Mapped[str] = mapped_column(String(64), nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_schema_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("prompt_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    prompt_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("context_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    context_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    max_json_bytes: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
