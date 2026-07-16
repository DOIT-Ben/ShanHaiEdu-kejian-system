"""add audit principal foreign keys

Revision ID: 3f62a6e7d901
Revises: 8dffee7f47f1
Create Date: 2026-07-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "3f62a6e7d901"
down_revision: str | Sequence[str] | None = "8dffee7f47f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_REFERENCES = (
    ("file_assets", "created_by"),
    ("file_assets", "updated_by"),
    ("file_asset_versions", "created_by"),
    ("projects", "created_by"),
    ("projects", "updated_by"),
    ("source_materials", "confirmed_by"),
    ("source_materials", "created_by"),
    ("source_materials", "updated_by"),
    ("generation_jobs", "created_by"),
    ("generation_jobs", "updated_by"),
    ("upload_sessions", "created_by"),
    ("upload_sessions", "updated_by"),
)


def upgrade() -> None:
    for table_name, column_name in AUDIT_REFERENCES:
        op.create_foreign_key(
            f"fk_{table_name}_{column_name}_principals",
            table_name,
            "principals",
            [column_name],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for table_name, column_name in reversed(AUDIT_REFERENCES):
        op.drop_constraint(
            f"fk_{table_name}_{column_name}_principals",
            table_name,
            type_="foreignkey",
        )
