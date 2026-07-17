"""Persistent model attempt and usage audit facts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base, utc_now


class GenerationAttempt(Base):
    __tablename__ = "generation_attempts"
    __table_args__ = (
        CheckConstraint("attempt_no > 0", name="attempt_no_positive"),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="status_allowed",
        ),
        CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="request_hash_format"),
        CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="latency_nonnegative"),
        CheckConstraint(
            "(status = 'running' AND finished_at IS NULL AND error_code IS NULL) OR "
            "(status = 'succeeded' AND finished_at IS NOT NULL AND error_code IS NULL "
            "AND latency_ms IS NOT NULL) OR "
            "(status IN ('failed', 'cancelled') AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL AND latency_ms IS NOT NULL)",
            name="terminal_fields_consistent",
        ),
        Index(
            "uq_generation_attempts_node_attempt",
            "node_run_id",
            "attempt_no",
            unique=True,
        ),
        Index(
            "uq_generation_attempts_organization_request",
            "organization_id",
            "request_id",
            unique=True,
        ),
        Index(
            "uq_generation_attempts_provider_request",
            "provider_name",
            "provider_request_id",
            unique=True,
            postgresql_where="provider_request_id IS NOT NULL",
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
    generation_job_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("generation_jobs.id", ondelete="RESTRICT")
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(String(160), nullable=False)
    capability: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(80))
    provider_model: Mapped[str | None] = mapped_column(String(160))
    route_reason: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(255))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(160))
    error_details_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="estimated_cost_nonnegative",
        ),
        CheckConstraint("actual_cost IS NULL OR actual_cost >= 0", name="actual_cost_nonnegative"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
        CheckConstraint("latency_ms >= 0", name="latency_nonnegative"),
        Index("uq_usage_records_attempt", "generation_attempt_id", unique=True),
        Index(
            "ix_usage_records_organization_project_created",
            "organization_id",
            "project_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    node_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("node_runs.id", ondelete="RESTRICT"), nullable=False
    )
    generation_attempt_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("generation_attempts.id", ondelete="RESTRICT"), nullable=False
    )
    capability: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(80))
    provider_model: Mapped[str | None] = mapped_column(String(160))
    input_units_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_units_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pricing_version: Mapped[str | None] = mapped_column(String(80))
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
