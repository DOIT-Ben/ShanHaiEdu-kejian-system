"""Add production identity sessions and login throttles.

Revision ID: l6g7h8i9j012
Revises: k5f6a7b8c910
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "l6g7h8i9j012"
down_revision: str | Sequence[str] | None = "k5f6a7b8c910"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_session_login_throttles",
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source_hash", name="pk_identity_session_login_throttles"),
    )
    op.create_table(
        "identity_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("csrf_nonce", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_from_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_identity_sessions_expires_after_creation"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_identity_sessions_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["principals.id"],
            name="fk_identity_sessions_principal_id_principals",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rotated_from_id"],
            ["identity_sessions.id"],
            name="fk_identity_sessions_rotated_from_id_identity_sessions",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_identity_sessions_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_identity_sessions"),
        sa.UniqueConstraint("rotated_from_id", name="uq_identity_sessions_rotated_from"),
        sa.UniqueConstraint("token_hash", name="uq_identity_sessions_token_hash"),
    )
    op.create_index("ix_identity_sessions_expires_at", "identity_sessions", ["expires_at"])
    op.create_index(
        "ix_identity_sessions_organization_id", "identity_sessions", ["organization_id"]
    )
    op.create_index("ix_identity_sessions_principal_id", "identity_sessions", ["principal_id"])
    op.create_index("ix_identity_sessions_revoked_at", "identity_sessions", ["revoked_at"])
    op.create_index("ix_identity_sessions_user_id", "identity_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_identity_sessions_user_id", table_name="identity_sessions")
    op.drop_index("ix_identity_sessions_revoked_at", table_name="identity_sessions")
    op.drop_index("ix_identity_sessions_principal_id", table_name="identity_sessions")
    op.drop_index("ix_identity_sessions_organization_id", table_name="identity_sessions")
    op.drop_index("ix_identity_sessions_expires_at", table_name="identity_sessions")
    op.drop_table("identity_sessions")
    op.drop_table("identity_session_login_throttles")
