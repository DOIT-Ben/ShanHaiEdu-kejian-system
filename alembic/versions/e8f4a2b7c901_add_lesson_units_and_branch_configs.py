"""Add lesson units and branch configurations.

Revision ID: e8f4a2b7c901
Revises: d7a4c12e91b3
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e8f4a2b7c901"
down_revision: str | Sequence[str] | None = "d7a4c12e91b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("lesson_division_version_id", sa.Uuid(), nullable=True))
    op.create_table(
        "lesson_units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_key", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("scope_summary", sa.Text(), nullable=False),
        sa.Column("objective_summary", sa.Text(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("source_division_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("position > 0", name="ck_lesson_units_position_positive"),
        sa.CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="ck_lesson_units_estimated_minutes_positive",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_lesson_units_status_allowed",
        ),
        sa.CheckConstraint("lock_version >= 1", name="ck_lesson_units_lock_version_positive"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_lesson_units_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_lesson_units_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["principals.id"],
            name="fk_lesson_units_created_by_principals",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["principals.id"],
            name="fk_lesson_units_updated_by_principals",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lesson_units"),
        sa.UniqueConstraint(
            "project_id",
            "lesson_key",
            name="uq_lesson_units_project_lesson_key",
        ),
        sa.UniqueConstraint(
            "project_id",
            "position",
            name="uq_lesson_units_project_position",
        ),
    )
    op.create_index("ix_lesson_units_project_id", "lesson_units", ["project_id"])
    op.create_table(
        "lesson_branch_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lesson_unit_id", sa.Uuid(), nullable=False),
        sa.Column("branch_key", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "branch_key IN ('lesson_plan', 'intro_options', 'ppt', 'video')",
            name="ck_lesson_branch_configs_branch_key_allowed",
        ),
        sa.CheckConstraint(
            "branch_key <> 'lesson_plan' OR enabled",
            name="ck_lesson_branch_configs_lesson_plan_enabled",
        ),
        sa.CheckConstraint(
            "lock_version >= 1",
            name="ck_lesson_branch_configs_lock_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_unit_id"],
            ["lesson_units.id"],
            name="fk_lesson_branch_configs_lesson_unit_id_lesson_units",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["principals.id"],
            name="fk_lesson_branch_configs_created_by_principals",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["principals.id"],
            name="fk_lesson_branch_configs_updated_by_principals",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lesson_branch_configs"),
        sa.UniqueConstraint(
            "lesson_unit_id",
            "branch_key",
            name="uq_lesson_branch_configs_lesson_branch",
        ),
    )
    op.create_index(
        "ix_lesson_branch_configs_lesson_unit_id",
        "lesson_branch_configs",
        ["lesson_unit_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lesson_branch_configs_lesson_unit_id",
        table_name="lesson_branch_configs",
    )
    op.drop_table("lesson_branch_configs")
    op.drop_index("ix_lesson_units_project_id", table_name="lesson_units")
    op.drop_table("lesson_units")
    op.drop_column("projects", "lesson_division_version_id")
