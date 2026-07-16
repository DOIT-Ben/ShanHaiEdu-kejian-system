from __future__ import annotations

import os

import psycopg
import pytest


@pytest.mark.integration
def test_ci_uses_real_postgresql() -> None:
    database_url = os.environ.get("SHANHAI_DATABASE_URL")
    if not database_url:
        pytest.skip("SHANHAI_DATABASE_URL is only configured for integration runs")

    with psycopg.connect(database_url, connect_timeout=5) as connection:
        version = connection.execute("select current_setting('server_version_num')").fetchone()

    assert version is not None
    assert int(version[0]) >= 160000
