from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import URL, make_url

from alembic import command

TEST_DATABASE_PREFIX = "shanhai_test_"


def require_postgres_url() -> URL:
    raw_url = os.environ.get("SHANHAI_DATABASE_URL")
    if not raw_url:
        pytest.skip("SHANHAI_DATABASE_URL is required for PostgreSQL integration tests")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("integration tests require PostgreSQL")
    return url


def psycopg_url(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


@pytest.fixture
def postgres_database_url() -> Iterator[str]:
    base_url = require_postgres_url()
    database_name = f"{TEST_DATABASE_PREFIX}{uuid4().hex[:12]}"
    if not database_name.startswith(TEST_DATABASE_PREFIX):
        raise RuntimeError("refusing to create a database outside the test prefix")
    admin_url = base_url.set(database="postgres")
    with psycopg.connect(psycopg_url(admin_url), autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    test_url = base_url.set(database=database_name)
    try:
        yield psycopg_url(test_url)
    finally:
        with psycopg.connect(psycopg_url(admin_url), autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name)))


def run_migration(database_url: str, revision: str) -> None:
    previous = os.environ.get("SHANHAI_DATABASE_URL")
    os.environ["SHANHAI_DATABASE_URL"] = database_url
    try:
        config = Config("alembic.ini")
        if revision == "base":
            command.downgrade(config, revision)
        else:
            command.upgrade(config, revision)
    finally:
        if previous is None:
            os.environ.pop("SHANHAI_DATABASE_URL", None)
        else:
            os.environ["SHANHAI_DATABASE_URL"] = previous


@pytest.fixture
def migrated_database_url(postgres_database_url: str) -> str:
    run_migration(postgres_database_url, "head")
    return postgres_database_url
