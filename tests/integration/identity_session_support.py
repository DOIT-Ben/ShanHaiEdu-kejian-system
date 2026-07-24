from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import FastAPI
from pydantic import SecretStr

from apps.api.database import build_session_factory
from apps.api.identity.models import Organization
from apps.api.settings import Settings
from tests.fakes.identity import TEST_PRINCIPAL_ID, seed_test_actor

APP_ORIGIN = "https://teacher.shanhai.test"


def runtime_settings(database_url: str, *, access_code: str, csrf_secret: str) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=database_url,
        session_access_code=SecretStr(access_code),
        session_csrf_secret=SecretStr(csrf_secret),
        session_teacher_principal_id=TEST_PRINCIPAL_ID,
        session_allowed_origins=[APP_ORIGIN],
        session_cookie_secure=True,
        session_ttl_seconds=3600,
        session_login_max_failures=3,
        session_login_window_seconds=60,
        session_trusted_proxy_hosts=["127.0.0.1"],
    )


def seed_teacher(app: FastAPI) -> None:
    factory = build_session_factory(app.state.database_engine)
    with factory() as session, session.begin():
        seed_test_actor(session)


def session_client(
    app: FastAPI,
    *,
    client_ip: str = "127.0.0.1",
) -> tuple[httpx.AsyncClient, httpx.ASGITransport]:
    transport = httpx.ASGITransport(app=app, client=(client_ip, 50421))
    return httpx.AsyncClient(transport=transport, base_url=APP_ORIGIN), transport


async def login(client: httpx.AsyncClient, access_code: str) -> httpx.Response:
    return await client.post(
        "/api/v2/auth/session",
        headers={"Origin": APP_ORIGIN},
        json={"access_code": access_code},
    )


async def create_project(
    client: httpx.AsyncClient,
    *,
    csrf_token: str,
    idempotency_key: str,
    title: str,
) -> httpx.Response:
    return await client.post(
        "/api/v2/projects",
        headers={
            "Idempotency-Key": idempotency_key,
            "Origin": APP_ORIGIN,
            "X-CSRF-Token": csrf_token,
        },
        json={"title": title, "knowledge_point": "1到5的认识"},
    )


def assert_secure_cookie(response: httpx.Response) -> None:
    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie
    assert "Domain=" not in set_cookie
    assert response.headers["cache-control"] == "no-store"
    exposed = {
        value.strip().lower()
        for value in response.headers["access-control-expose-headers"].split(",")
    }
    assert {"etag", "x-request-id"}.issubset(exposed)


def seed_other_organization(app: FastAPI, organization_id: UUID) -> None:
    factory = build_session_factory(app.state.database_engine)
    with factory() as session, session.begin():
        session.add(
            Organization(
                id=organization_id,
                slug="other-school",
                name="Other School",
                status="active",
                created_at=datetime.now(UTC),
            )
        )
