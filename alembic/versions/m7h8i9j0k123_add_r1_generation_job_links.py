"""Add exact R1 generation job links.

Revision ID: m7h8i9j0k123
Revises: l6g7h8i9j012
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "m7h8i9j0k123"
down_revision: str | Sequence[str] | None = "l6g7h8i9j012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("node_run_id", sa.Uuid(), nullable=True))
    op.add_column("generation_jobs", sa.Column("lesson_unit_id", sa.Uuid(), nullable=True))
    op.add_column(
        "generation_jobs",
        sa.Column("result_artifact_version_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_generation_jobs_node_run_id_node_runs",
        "generation_jobs",
        "node_runs",
        ["node_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_generation_jobs_lesson_unit_id_lesson_units",
        "generation_jobs",
        "lesson_units",
        ["lesson_unit_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_generation_jobs_result_artifact_version_id_artifact_versions",
        "generation_jobs",
        "artifact_versions",
        ["result_artifact_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_generation_jobs_organization_project_id",
        "generation_jobs",
        ["organization_id", "project_id", "id"],
    )
    op.create_index(
        "ix_generation_jobs_organization_project_lesson_id",
        "generation_jobs",
        ["organization_id", "project_id", "lesson_unit_id", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generation_jobs_organization_project_lesson_id",
        table_name="generation_jobs",
    )
    op.drop_index(
        "ix_generation_jobs_organization_project_id",
        table_name="generation_jobs",
    )
    op.drop_constraint(
        "fk_generation_jobs_result_artifact_version_id_artifact_versions",
        "generation_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_generation_jobs_lesson_unit_id_lesson_units",
        "generation_jobs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_generation_jobs_node_run_id_node_runs",
        "generation_jobs",
        type_="foreignkey",
    )
    op.drop_column("generation_jobs", "result_artifact_version_id")
    op.drop_column("generation_jobs", "lesson_unit_id")
    op.drop_column("generation_jobs", "node_run_id")
