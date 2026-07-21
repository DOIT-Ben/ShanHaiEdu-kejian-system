"""Persist immutable node-execution package lineage."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "g1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f2a7b9c1d304"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "creation_packages",
        sa.Column("source_artifact_version_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "creation_packages",
        sa.Column("lesson_unit_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "creation_package_items",
        sa.Column(
            "reference_assets_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_table(
        "node_execution_leases",
        sa.Column("node_run_id", sa.Uuid(), nullable=False),
        sa.Column("owner_token", sa.String(length=64), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["node_run_id"], ["node_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("node_run_id"),
    )
    op.create_foreign_key(
        "fk_creation_packages_source_artifact_version",
        "creation_packages",
        "artifact_versions",
        ["source_artifact_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_creation_packages_lesson_unit",
        "creation_packages",
        "lesson_units",
        ["lesson_unit_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_creation_packages_source_artifact_version",
        "creation_packages",
        ["organization_id", "source_artifact_version_id"],
    )
    op.create_table(
        "node_execution_recovery_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("node_run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=160), nullable=False),
        sa.Column("owner_token", sa.String(length=64), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=False),
        sa.Column("output_schema_digest", sa.String(length=64), nullable=False),
        sa.Column("prompt_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("context_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("context_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("max_json_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["node_run_id"], ["node_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["attempt_id"], ["generation_attempts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["prompt_snapshot_id"], ["prompt_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["context_snapshot_id"], ["context_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_node_execution_recovery_fact_attempt",
        "node_execution_recovery_facts",
        ["organization_id", "node_run_id", "attempt_id"],
        unique=True,
    )
    op.create_index(
        "ix_node_execution_recovery_fact_expiry",
        "node_execution_recovery_facts",
        ["organization_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_node_execution_recovery_fact_expiry",
        table_name="node_execution_recovery_facts",
    )
    op.drop_index(
        "uq_node_execution_recovery_fact_attempt",
        table_name="node_execution_recovery_facts",
    )
    op.drop_table("node_execution_recovery_facts")
    op.drop_index(
        "ix_creation_packages_source_artifact_version",
        table_name="creation_packages",
    )
    op.drop_constraint(
        "fk_creation_packages_lesson_unit",
        "creation_packages",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_creation_packages_source_artifact_version",
        "creation_packages",
        type_="foreignkey",
    )
    op.drop_column("creation_package_items", "reference_assets_json")
    op.drop_table("node_execution_leases")
    op.drop_column("creation_packages", "lesson_unit_id")
    op.drop_column("creation_packages", "source_artifact_version_id")
