"""Add prompt snapshots and model usage audit.

Revision ID: a9e1f3c5b704
Revises: c8d0e2f4a603
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a9e1f3c5b704"
down_revision: str | Sequence[str] | None = "c8d0e2f4a603"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_context_snapshots()
    _create_prompt_snapshots()
    _create_generation_attempts()
    _create_usage_records()
    _link_artifact_snapshots()
    _create_immutability_triggers()


def downgrade() -> None:
    _drop_immutability_triggers()
    op.drop_constraint(
        "fk_artifact_versions_prompt_snapshot",
        "artifact_versions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_artifact_versions_context_snapshot",
        "artifact_versions",
        type_="foreignkey",
    )
    op.drop_index("ix_usage_records_organization_project_created", table_name="usage_records")
    op.drop_index("uq_usage_records_attempt", table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_index("uq_generation_attempts_provider_request", table_name="generation_attempts")
    op.drop_index("uq_generation_attempts_organization_request", table_name="generation_attempts")
    op.drop_index("uq_generation_attempts_node_attempt", table_name="generation_attempts")
    op.drop_table("generation_attempts")
    op.drop_index("ix_prompt_snapshots_organization_project_created", table_name="prompt_snapshots")
    op.drop_index("uq_prompt_snapshots_context", table_name="prompt_snapshots")
    op.drop_index("uq_prompt_snapshots_node_run", table_name="prompt_snapshots")
    op.drop_table("prompt_snapshots")
    op.drop_index(
        "ix_context_snapshots_organization_project_created", table_name="context_snapshots"
    )
    op.drop_index("uq_context_snapshots_node_run", table_name="context_snapshots")
    op.drop_table("context_snapshots")


def _create_context_snapshots() -> None:
    op.create_table(
        "context_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("node_run_id", sa.Uuid(), nullable=False),
        sa.Column("bindings_json", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_context_snapshots_content_hash_format",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["node_run_id"], ["node_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_context_snapshots"),
    )
    op.create_index(
        "uq_context_snapshots_node_run", "context_snapshots", ["node_run_id"], unique=True
    )
    op.create_index(
        "ix_context_snapshots_organization_project_created",
        "context_snapshots",
        ["organization_id", "project_id", "created_at"],
    )


def _create_prompt_snapshots() -> None:
    op.create_table(
        "prompt_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("node_run_id", sa.Uuid(), nullable=False),
        sa.Column("context_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("template_refs_json", postgresql.JSONB(), nullable=False),
        sa.Column("layers_json", postgresql.JSONB(), nullable=False),
        sa.Column("editable_prompt", sa.Text(), nullable=False),
        sa.Column("user_diff_json", postgresql.JSONB(), nullable=False),
        sa.Column("compiled_prompt", sa.Text(), nullable=False),
        sa.Column("request_schema_json", postgresql.JSONB(), nullable=False),
        sa.Column("preview_json", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_prompt_snapshots_content_hash_format",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["node_run_id"], ["node_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["context_snapshot_id"], ["context_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["principals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_snapshots"),
    )
    op.create_index(
        "uq_prompt_snapshots_node_run", "prompt_snapshots", ["node_run_id"], unique=True
    )
    op.create_index(
        "uq_prompt_snapshots_context", "prompt_snapshots", ["context_snapshot_id"], unique=True
    )
    op.create_index(
        "ix_prompt_snapshots_organization_project_created",
        "prompt_snapshots",
        ["organization_id", "project_id", "created_at"],
    )


def _create_generation_attempts() -> None:
    op.create_table(
        "generation_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("node_run_id", sa.Uuid(), nullable=False),
        sa.Column("generation_job_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=160), nullable=False),
        sa.Column("capability", sa.String(length=160), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=True),
        sa.Column("provider_model", sa.String(length=160), nullable=True),
        sa.Column("route_reason", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=160), nullable=True),
        sa.Column("error_details_json", postgresql.JSONB(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.CheckConstraint("attempt_no > 0", name="ck_generation_attempts_attempt_no_positive"),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="ck_generation_attempts_status_allowed",
        ),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="ck_generation_attempts_request_hash_format",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_generation_attempts_latency_nonnegative",
        ),
        sa.CheckConstraint(
            "(status = 'running' AND finished_at IS NULL AND error_code IS NULL) OR "
            "(status = 'succeeded' AND finished_at IS NOT NULL AND error_code IS NULL "
            "AND latency_ms IS NOT NULL) OR "
            "(status IN ('failed', 'cancelled') AND finished_at IS NOT NULL "
            "AND error_code IS NOT NULL AND latency_ms IS NOT NULL)",
            name="ck_generation_attempts_terminal_fields_consistent",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["node_run_id"], ["node_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["generation_job_id"], ["generation_jobs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_generation_attempts"),
    )
    op.create_index(
        "uq_generation_attempts_node_attempt",
        "generation_attempts",
        ["node_run_id", "attempt_no"],
        unique=True,
    )
    op.create_index(
        "uq_generation_attempts_organization_request",
        "generation_attempts",
        ["organization_id", "request_id"],
        unique=True,
    )
    op.create_index(
        "uq_generation_attempts_provider_request",
        "generation_attempts",
        ["provider_name", "provider_request_id"],
        unique=True,
        postgresql_where=sa.text("provider_request_id IS NOT NULL"),
    )


def _create_usage_records() -> None:
    op.create_table(
        "usage_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("node_run_id", sa.Uuid(), nullable=False),
        sa.Column("generation_attempt_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(length=160), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=True),
        sa.Column("provider_model", sa.String(length=160), nullable=True),
        sa.Column("input_units_json", postgresql.JSONB(), nullable=False),
        sa.Column("output_units_json", postgresql.JSONB(), nullable=False),
        sa.Column("pricing_version", sa.String(length=80), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("actual_cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="ck_usage_records_estimated_cost_nonnegative",
        ),
        sa.CheckConstraint(
            "actual_cost IS NULL OR actual_cost >= 0",
            name="ck_usage_records_actual_cost_nonnegative",
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_usage_records_currency_format"),
        sa.CheckConstraint("latency_ms >= 0", name="ck_usage_records_latency_nonnegative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["node_run_id"], ["node_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["generation_attempt_id"], ["generation_attempts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_records"),
    )
    op.create_index(
        "uq_usage_records_attempt", "usage_records", ["generation_attempt_id"], unique=True
    )
    op.create_index(
        "ix_usage_records_organization_project_created",
        "usage_records",
        ["organization_id", "project_id", "created_at"],
    )


def _link_artifact_snapshots() -> None:
    op.create_foreign_key(
        "fk_artifact_versions_context_snapshot",
        "artifact_versions",
        "context_snapshots",
        ["context_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_artifact_versions_prompt_snapshot",
        "artifact_versions",
        "prompt_snapshots",
        ["prompt_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def _create_immutability_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION forbid_prompt_audit_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION '% rows are append-only', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_context_snapshots_append_only
        BEFORE UPDATE OR DELETE ON context_snapshots
        FOR EACH ROW EXECUTE FUNCTION forbid_prompt_audit_mutation();

        CREATE TRIGGER trg_prompt_snapshots_append_only
        BEFORE UPDATE OR DELETE ON prompt_snapshots
        FOR EACH ROW EXECUTE FUNCTION forbid_prompt_audit_mutation();

        CREATE TRIGGER trg_usage_records_append_only
        BEFORE UPDATE OR DELETE ON usage_records
        FOR EACH ROW EXECUTE FUNCTION forbid_prompt_audit_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION protect_generation_attempt_identity() RETURNS trigger AS $$
        BEGIN
          IF OLD.status <> 'running' THEN
            RAISE EXCEPTION 'terminal generation attempts are immutable';
          END IF;
          IF NEW.id IS DISTINCT FROM OLD.id
             OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.node_run_id IS DISTINCT FROM OLD.node_run_id
             OR NEW.generation_job_id IS DISTINCT FROM OLD.generation_job_id
             OR NEW.attempt_no IS DISTINCT FROM OLD.attempt_no
             OR NEW.request_id IS DISTINCT FROM OLD.request_id
             OR NEW.capability IS DISTINCT FROM OLD.capability
             OR NEW.provider_name IS DISTINCT FROM OLD.provider_name
             OR NEW.provider_model IS DISTINCT FROM OLD.provider_model
             OR NEW.route_reason IS DISTINCT FROM OLD.route_reason
             OR NEW.request_hash IS DISTINCT FROM OLD.request_hash
             OR NEW.submitted_at IS DISTINCT FROM OLD.submitted_at THEN
            RAISE EXCEPTION 'generation attempt identity is immutable';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_generation_attempt_identity
        BEFORE UPDATE OR DELETE ON generation_attempts
        FOR EACH ROW EXECUTE FUNCTION protect_generation_attempt_identity();
        """
    )


def _drop_immutability_triggers() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_generation_attempt_identity ON generation_attempts;
        DROP FUNCTION IF EXISTS protect_generation_attempt_identity();
        DROP TRIGGER IF EXISTS trg_usage_records_append_only ON usage_records;
        DROP TRIGGER IF EXISTS trg_prompt_snapshots_append_only ON prompt_snapshots;
        DROP TRIGGER IF EXISTS trg_context_snapshots_append_only ON context_snapshots;
        DROP FUNCTION IF EXISTS forbid_prompt_audit_mutation();
        """
    )
