from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from apps.api.database import sqlalchemy_url
from tests.conftest import run_migration

EXPECTED_TABLES = {
    "alembic_version",
    "file_asset_versions",
    "file_assets",
    "generation_jobs",
    "idempotency_records",
    "organizations",
    "outbox_events",
    "principals",
    "projects",
    "event_stream_entries",
    "source_materials",
    "upload_sessions",
}


def test_empty_database_upgrade_downgrade_upgrade(postgres_database_url: str) -> None:
    config = Config("alembic.ini")
    run_migration(postgres_database_url, "head")
    engine = create_engine(sqlalchemy_url(postgres_database_url))
    assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))

    run_migration(postgres_database_url, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}

    run_migration(postgres_database_url, "head")
    assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))

    assert ScriptDirectory.from_config(config).get_current_head() == "c6b7d8e9f001"
