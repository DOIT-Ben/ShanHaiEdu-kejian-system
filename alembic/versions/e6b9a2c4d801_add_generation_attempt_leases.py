"""Add generation attempt leases and atomic attempt counters.

Revision ID: e6b9a2c4d801
Revises: c2d4e6f8a901
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6b9a2c4d801"
down_revision: str | Sequence[str] | None = "c2d4e6f8a901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_attempts",
        sa.Column("operation_kind", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "generation_attempts",
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "generation_attempts",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_attempts",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_attempts",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE generation_attempts SET operation_kind = 'legacy_unknown', "
        "lease_owner = CASE WHEN status = 'running' THEN 'migration:expired' END, "
        "heartbeat_at = CASE WHEN status = 'running' "
        "THEN LEAST(submitted_at, now() - interval '2 microseconds') END, "
        "lease_expires_at = CASE WHEN status = 'running' "
        "THEN LEAST(submitted_at + interval '1 microsecond', "
        "now() - interval '1 microsecond') END"
    )
    op.alter_column("generation_attempts", "operation_kind", nullable=False)

    op.drop_constraint(
        "ck_generation_attempts_status_allowed",
        "generation_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_generation_attempts_terminal_fields_consistent",
        "generation_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_generation_attempts_status_allowed",
        "generation_attempts",
        "status IN ('running', 'succeeded', 'failed', 'cancelled', 'submission_unknown')",
    )
    op.create_check_constraint(
        "ck_generation_attempts_operation_kind_allowed",
        "generation_attempts",
        "operation_kind IN ('text_generate', 'image_generate', 'video_submit', "
        "'video_poll', 'video_cancel', 'legacy_unknown')",
    )
    op.create_check_constraint(
        "ck_generation_attempts_terminal_fields_consistent",
        "generation_attempts",
        "(status = 'running' AND finished_at IS NULL AND error_code IS NULL "
        "AND latency_ms IS NULL AND lease_owner IS NOT NULL "
        "AND lease_expires_at IS NOT NULL AND heartbeat_at IS NOT NULL) OR "
        "(status = 'succeeded' AND finished_at IS NOT NULL AND error_code IS NULL "
        "AND latency_ms IS NOT NULL AND lease_owner IS NULL "
        "AND lease_expires_at IS NULL) OR "
        "(status IN ('failed', 'cancelled', 'submission_unknown') "
        "AND finished_at IS NOT NULL AND error_code IS NOT NULL "
        "AND latency_ms IS NOT NULL AND lease_owner IS NULL "
        "AND lease_expires_at IS NULL)",
    )
    op.create_check_constraint(
        "ck_generation_attempts_lease_window_positive",
        "generation_attempts",
        "lease_expires_at IS NULL OR heartbeat_at IS NULL "
        "OR lease_expires_at > heartbeat_at",
    )
    op.create_index(
        "ix_generation_attempts_status_lease",
        "generation_attempts",
        ["status", "lease_expires_at"],
    )

    op.create_table(
        "generation_attempt_counters",
        sa.Column("node_run_id", sa.Uuid(), nullable=False),
        sa.Column("next_attempt_no", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "next_attempt_no > 0",
            name="ck_generation_attempt_counters_next_attempt_no_positive",
        ),
        sa.ForeignKeyConstraint(
            ["node_run_id"],
            ["node_runs.id"],
            name="fk_generation_attempt_counters_node_run_id_node_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("node_run_id", name="pk_generation_attempt_counters"),
    )
    op.execute(
        "INSERT INTO generation_attempt_counters (node_run_id, next_attempt_no) "
        "SELECT node_run_id, max(attempt_no) + 1 FROM generation_attempts GROUP BY node_run_id"
    )
    _replace_attempt_identity_trigger(include_operation_kind=True)
    _create_usage_terminal_trigger()


def downgrade() -> None:
    op.execute(
        "UPDATE generation_attempts SET status = 'failed' "
        "WHERE status = 'submission_unknown'"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_usage_record_terminal_attempt ON usage_records; "
        "DROP FUNCTION IF EXISTS require_terminal_generation_attempt();"
    )
    _replace_attempt_identity_trigger(include_operation_kind=False)
    op.drop_table("generation_attempt_counters")
    op.drop_index("ix_generation_attempts_status_lease", table_name="generation_attempts")
    op.drop_constraint(
        "ck_generation_attempts_lease_window_positive",
        "generation_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_generation_attempts_terminal_fields_consistent",
        "generation_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_generation_attempts_operation_kind_allowed",
        "generation_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_generation_attempts_status_allowed",
        "generation_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_generation_attempts_status_allowed",
        "generation_attempts",
        "status IN ('running', 'succeeded', 'failed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_generation_attempts_terminal_fields_consistent",
        "generation_attempts",
        "(status = 'running' AND finished_at IS NULL AND error_code IS NULL) OR "
        "(status = 'succeeded' AND finished_at IS NOT NULL AND error_code IS NULL "
        "AND latency_ms IS NOT NULL) OR "
        "(status IN ('failed', 'cancelled') AND finished_at IS NOT NULL "
        "AND error_code IS NOT NULL AND latency_ms IS NOT NULL)",
    )
    op.drop_column("generation_attempts", "cancel_requested_at")
    op.drop_column("generation_attempts", "heartbeat_at")
    op.drop_column("generation_attempts", "lease_expires_at")
    op.drop_column("generation_attempts", "lease_owner")
    op.drop_column("generation_attempts", "operation_kind")


def _replace_attempt_identity_trigger(*, include_operation_kind: bool) -> None:
    operation_check = (
        "OR NEW.operation_kind IS DISTINCT FROM OLD.operation_kind" if include_operation_kind else ""
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION protect_generation_attempt_identity() RETURNS trigger AS $$
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
             {operation_check}
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
        """
    )


def _create_usage_terminal_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION require_terminal_generation_attempt() RETURNS trigger AS $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM generation_attempts
            WHERE id = NEW.generation_attempt_id
              AND organization_id = NEW.organization_id
              AND project_id = NEW.project_id
              AND node_run_id = NEW.node_run_id
              AND status IN ('succeeded', 'failed', 'cancelled', 'submission_unknown')
          ) THEN
            RAISE EXCEPTION 'usage records require a matching terminal generation attempt';
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_usage_record_terminal_attempt
        BEFORE INSERT ON usage_records
        FOR EACH ROW EXECUTE FUNCTION require_terminal_generation_attempt();
        """
    )
