"""Allow audited deterministic executor attempts.

Revision ID: k5f6a7b8c910
Revises: j4e5f6a7b809
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "k5f6a7b8c910"
down_revision: str | Sequence[str] | None = "j4e5f6a7b809"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CURRENT_VALUES = (
    "'text_generate', 'image_generate', 'video_submit', 'video_poll', "
    "'video_cancel', 'deterministic_execute', 'legacy_unknown'"
)
_PREVIOUS_VALUES = (
    "'text_generate', 'image_generate', 'video_submit', 'video_poll', "
    "'video_cancel', 'legacy_unknown'"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_generation_attempts_operation_kind_allowed",
        "generation_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_generation_attempts_operation_kind_allowed",
        "generation_attempts",
        f"operation_kind IN ({_CURRENT_VALUES})",
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_generation_attempt_identity ON generation_attempts")
    op.execute(
        "UPDATE generation_attempts SET operation_kind = 'legacy_unknown' "
        "WHERE operation_kind = 'deterministic_execute'"
    )
    op.drop_constraint(
        "ck_generation_attempts_operation_kind_allowed",
        "generation_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_generation_attempts_operation_kind_allowed",
        "generation_attempts",
        f"operation_kind IN ({_PREVIOUS_VALUES})",
    )
    op.execute(
        "CREATE TRIGGER trg_generation_attempt_identity "
        "BEFORE UPDATE OR DELETE ON generation_attempts "
        "FOR EACH ROW EXECUTE FUNCTION protect_generation_attempt_identity()"
    )
