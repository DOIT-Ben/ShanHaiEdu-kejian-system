"""Add immutable artifact quality reports."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "h2c3d4e5f607"
down_revision: str | Sequence[str] | None = "g1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABILITY_FUNCTION = "reject_artifact_quality_report_mutation"
_IMMUTABILITY_TRIGGER = "trg_artifact_quality_reports_immutable"


def upgrade() -> None:
    op.create_table(
        "artifact_quality_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_unit_id", sa.Uuid(), nullable=True),
        sa.Column("source_artifact_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_release_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_definition_version_id", sa.Uuid(), nullable=False),
        sa.Column("validate_node_run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "validator_set_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("validator_set_hash", sa.String(length=64), nullable=False),
        sa.Column("conclusion", sa.String(length=20), nullable=False),
        sa.Column(
            "findings_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "source_content_hash ~ '^[0-9a-f]{64}$'",
            name="source_content_hash_format",
        ),
        sa.CheckConstraint(
            "validator_set_hash ~ '^[0-9a-f]{64}$'",
            name="validator_set_hash_format",
        ),
        sa.CheckConstraint(
            "evidence_hash ~ '^[0-9a-f]{64}$'",
            name="evidence_hash_format",
        ),
        sa.CheckConstraint(
            "conclusion IN ('passed', 'failed')",
            name="conclusion_allowed",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(validator_set_json) = 'array' "
            "AND jsonb_array_length(validator_set_json) > 0",
            name="validator_set_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(findings_json) = 'array'",
            name="findings_array",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_artifact_quality_reports_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_artifact_quality_reports_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_unit_id"],
            ["lesson_units.id"],
            name="fk_artifact_quality_reports_lesson_unit",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_version_id"],
            ["artifact_versions.id"],
            name="fk_artifact_quality_reports_source_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["content_release_id"],
            ["content_releases.id"],
            name="fk_artifact_quality_reports_content_release",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_definition_version_id"],
            ["workflow_definition_versions.id"],
            name="fk_artifact_quality_reports_workflow_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validate_node_run_id"],
            ["node_runs.id"],
            name="fk_artifact_quality_reports_validate_node_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["principals.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_artifact_quality_reports_source_workflow_validators",
        "artifact_quality_reports",
        [
            "source_artifact_version_id",
            "workflow_definition_version_id",
            "validator_set_hash",
        ],
        unique=True,
    )
    op.create_index(
        "uq_artifact_quality_reports_validate_node_run",
        "artifact_quality_reports",
        ["validate_node_run_id"],
        unique=True,
    )
    op.create_index(
        "ix_artifact_quality_reports_project_source",
        "artifact_quality_reports",
        ["organization_id", "project_id", "source_artifact_version_id"],
    )
    op.execute(
        f"""
        CREATE FUNCTION {_IMMUTABILITY_FUNCTION}() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'artifact quality reports are append-only';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER {_IMMUTABILITY_TRIGGER}
        BEFORE UPDATE OR DELETE ON artifact_quality_reports
        FOR EACH ROW EXECUTE FUNCTION {_IMMUTABILITY_FUNCTION}();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_IMMUTABILITY_TRIGGER} ON artifact_quality_reports")
    op.execute(f"DROP FUNCTION IF EXISTS {_IMMUTABILITY_FUNCTION}()")
    op.drop_index(
        "ix_artifact_quality_reports_project_source",
        table_name="artifact_quality_reports",
    )
    op.drop_index(
        "uq_artifact_quality_reports_validate_node_run",
        table_name="artifact_quality_reports",
    )
    op.drop_index(
        "uq_artifact_quality_reports_source_workflow_validators",
        table_name="artifact_quality_reports",
    )
    op.drop_table("artifact_quality_reports")
