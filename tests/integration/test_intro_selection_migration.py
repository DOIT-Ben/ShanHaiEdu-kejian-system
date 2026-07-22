from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from apps.api.database import sqlalchemy_url


def test_intro_selection_migration_exposes_constraints_and_guard_triggers(
    migrated_database_url: str,
) -> None:
    engine = create_engine(sqlalchemy_url(migrated_database_url))
    try:
        inspector = inspect(engine)
        assert "intro_selections" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("intro_selections")}
        assert {
            "id",
            "organization_id",
            "project_id",
            "lesson_unit_id",
            "artifact_version_id",
            "source_approval_id",
            "selection_method",
            "option_key",
            "snapshot_json",
            "actor_type",
            "actor_user_id",
            "policy_evidence_json",
            "recommendation_evidence_json",
            "reason",
            "active",
            "selected_at",
            "deactivated_at",
        } <= columns
        indexes = {index["name"]: index for index in inspector.get_indexes("intro_selections")}
        active = indexes["uq_intro_selections_lesson_active"]
        assert active["unique"] is True
        assert active["column_names"] == ["organization_id", "lesson_unit_id"]
        with engine.connect() as connection:
            triggers = set(
                connection.execute(
                    text(
                        "SELECT tgname FROM pg_trigger "
                        "WHERE tgrelid = 'intro_selections'::regclass AND NOT tgisinternal"
                    )
                ).scalars()
            )
        assert "trg_intro_selections_scope" in triggers
        assert "trg_intro_selections_guard_mutation" in triggers
    finally:
        engine.dispose()
