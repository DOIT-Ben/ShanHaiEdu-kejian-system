"""Add recoverable provider task identity.

Revision ID: f1a6c3e9b205
Revises: e4f6a8c0b702
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a6c3e9b205"
down_revision: str | Sequence[str] | None = "e4f6a8c0b702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_attempts",
        sa.Column("provider_task_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_generation_attempts_provider_task",
        "generation_attempts",
        ["provider_name", "provider_task_id"],
        unique=False,
        postgresql_where=sa.text("provider_task_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_generation_attempts_provider_task",
        table_name="generation_attempts",
    )
    op.drop_column("generation_attempts", "provider_task_id")
