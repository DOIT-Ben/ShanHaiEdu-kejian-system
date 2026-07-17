"""Link material parse versions to their generation jobs.

Revision ID: c8d0e2f4a603
Revises: b7c9d1e3f502
Create Date: 2026-07-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c8d0e2f4a603"
down_revision = "b7c9d1e3f502"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "material_parse_versions",
        sa.Column("generation_job_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_material_parse_versions_generation_job",
        "material_parse_versions",
        "generation_jobs",
        ["generation_job_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "uq_material_parse_versions_generation_job",
        "material_parse_versions",
        ["generation_job_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_material_parse_versions_generation_job",
        table_name="material_parse_versions",
    )
    op.drop_constraint(
        "fk_material_parse_versions_generation_job",
        "material_parse_versions",
        type_="foreignkey",
    )
    op.drop_column("material_parse_versions", "generation_job_id")
