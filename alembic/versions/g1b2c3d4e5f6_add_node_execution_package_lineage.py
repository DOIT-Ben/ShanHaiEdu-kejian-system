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


def downgrade() -> None:
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
    op.drop_column("creation_packages", "lesson_unit_id")
    op.drop_column("creation_packages", "source_artifact_version_id")
