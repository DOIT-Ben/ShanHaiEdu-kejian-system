from __future__ import annotations

from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy import select

from apps.api.database import build_session_factory
from apps.api.identity.models import Session as IdentitySession
from apps.api.main import create_app
from tests.integration.identity_session_support import (
    APP_ORIGIN,
    create_project,
    login,
    runtime_settings,
    seed_other_organization,
    seed_teacher,
    session_client,
)


async def test_authenticated_write_rejects_missing_or_wrong_csrf(
    migrated_database_url: str,
) -> None:
    access_code = token_urlsafe(32)
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=access_code,
            csrf_secret=token_urlsafe(48),
        )
    )
    seed_teacher(app)
    try:
        client, _ = session_client(app)
        async with client:
            created = await login(client, access_code)
            assert created.status_code == 201, created.text
            missing = await client.post(
                "/api/v2/projects",
                headers={"Idempotency-Key": "runtime-auth-missing-csrf", "Origin": APP_ORIGIN},
                json={"title": "无 CSRF", "knowledge_point": "1到5的认识"},
            )
            wrong = await create_project(
                client,
                csrf_token="0" * 64,
                idempotency_key="runtime-auth-wrong-csrf",
                title="错误 CSRF",
            )
        assert missing.status_code == 403
        assert wrong.status_code == 403
        assert missing.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
        assert wrong.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"
    finally:
        app.state.database_engine.dispose()


async def test_authenticated_write_rejects_wrong_origin(
    migrated_database_url: str,
) -> None:
    access_code = token_urlsafe(32)
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=access_code,
            csrf_secret=token_urlsafe(48),
        )
    )
    seed_teacher(app)
    try:
        client, _ = session_client(app)
        async with client:
            created = await login(client, access_code)
            csrf_token = created.json()["data"]["csrf_token"]
            wrong_origin = await client.post(
                "/api/v2/projects",
                headers={
                    "Idempotency-Key": "runtime-auth-wrong-origin",
                    "Origin": "https://evil.example",
                    "X-CSRF-Token": csrf_token,
                },
                json={"title": "错误来源", "knowledge_point": "1到5的认识"},
            )
        assert wrong_origin.status_code == 403
        assert wrong_origin.json()["error"]["code"] == "ORIGIN_FORBIDDEN"
    finally:
        app.state.database_engine.dispose()


async def test_login_rejects_wrong_origin(migrated_database_url: str) -> None:
    access_code = token_urlsafe(32)
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=access_code,
            csrf_secret=token_urlsafe(48),
        )
    )
    try:
        client, _ = session_client(app)
        async with client:
            rejected = await client.post(
                "/api/v2/auth/session",
                headers={"Origin": "https://evil.example"},
                json={"access_code": access_code},
            )
        assert rejected.status_code == 403
        assert rejected.json()["error"]["code"] == "ORIGIN_FORBIDDEN"
    finally:
        app.state.database_engine.dispose()


async def test_untrusted_forwarded_ip_cannot_bypass_rate_limit(
    migrated_database_url: str,
) -> None:
    access_code = token_urlsafe(32)
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=access_code,
            csrf_secret=token_urlsafe(48),
        )
    )
    try:
        client, _ = session_client(app, client_ip="198.51.100.20")
        async with client:
            for index in range(3):
                rejected = await client.post(
                    "/api/v2/auth/session",
                    headers={
                        "Origin": APP_ORIGIN,
                        "X-Forwarded-For": f"203.0.113.{index + 1}",
                    },
                    json={"access_code": token_urlsafe(16)},
                )
                assert rejected.status_code == 401
            limited = await client.post(
                "/api/v2/auth/session",
                headers={"Origin": APP_ORIGIN, "X-Forwarded-For": "203.0.113.99"},
                json={"access_code": access_code},
            )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "LOGIN_RATE_LIMITED"
    finally:
        app.state.database_engine.dispose()


async def test_trusted_proxy_appended_client_ip_cannot_bypass_rate_limit(
    migrated_database_url: str,
) -> None:
    access_code = token_urlsafe(32)
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=access_code,
            csrf_secret=token_urlsafe(48),
        )
    )
    seed_teacher(app)
    try:
        client, _ = session_client(app)
        async with client:
            for index in range(3):
                rejected = await client.post(
                    "/api/v2/auth/session",
                    headers={
                        "Origin": APP_ORIGIN,
                        "X-Forwarded-For": f"203.0.113.{index + 1}, 198.51.100.20",
                    },
                    json={"access_code": token_urlsafe(16)},
                )
                assert rejected.status_code == 401
            limited = await client.post(
                "/api/v2/auth/session",
                headers={
                    "Origin": APP_ORIGIN,
                    "X-Forwarded-For": "203.0.113.99, 198.51.100.20",
                },
                json={"access_code": access_code},
            )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "LOGIN_RATE_LIMITED"
    finally:
        app.state.database_engine.dispose()


async def test_expired_session_is_rejected(migrated_database_url: str) -> None:
    access_code = token_urlsafe(32)
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=access_code,
            csrf_secret=token_urlsafe(48),
        )
    )
    seed_teacher(app)
    factory = build_session_factory(app.state.database_engine)
    try:
        client, _ = session_client(app)
        async with client:
            created = await login(client, access_code)
            assert created.status_code == 201
            with factory() as session, session.begin():
                persisted = session.scalar(select(IdentitySession))
                assert persisted is not None
                expired_at = datetime.now(UTC) - timedelta(seconds=1)
                persisted.created_at = expired_at - timedelta(hours=1)
                persisted.expires_at = expired_at
            expired = await client.get("/api/v2/auth/session")
        assert expired.status_code == 401
        assert expired.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
        with factory() as session:
            persisted = session.scalar(select(IdentitySession))
            assert persisted is not None
            assert persisted.revoked_at is None
    finally:
        app.state.database_engine.dispose()


async def test_oversized_login_is_rejected(migrated_database_url: str) -> None:
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=token_urlsafe(32),
            csrf_secret=token_urlsafe(48),
        )
    )
    try:
        client, _ = session_client(app)
        async with client:
            oversized = await client.post(
                "/api/v2/auth/session",
                headers={"Content-Type": "application/json", "Origin": APP_ORIGIN},
                content=b'{"access_code":"' + (b"x" * 2_100) + b'"}',
            )
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "REQUEST_TOO_LARGE"
    finally:
        app.state.database_engine.dispose()


async def test_session_rejects_cross_tenant_facts(migrated_database_url: str) -> None:
    access_code = token_urlsafe(32)
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=access_code,
            csrf_secret=token_urlsafe(48),
        )
    )
    seed_teacher(app)
    factory = build_session_factory(app.state.database_engine)
    try:
        client, _ = session_client(app)
        async with client:
            created = await login(client, access_code)
            assert created.status_code == 201
            other_id = UUID("01900000-0000-7000-8000-000000000199")
            seed_other_organization(app, other_id)
            with factory() as session, session.begin():
                persisted = session.scalar(select(IdentitySession))
                assert persisted is not None
                persisted.organization_id = other_id
            tampered = await client.get("/api/v2/auth/session")
        assert tampered.status_code == 401
        assert tampered.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
        with factory() as session:
            persisted = session.scalar(select(IdentitySession))
            assert persisted is not None
            assert persisted.revoked_at is None
    finally:
        app.state.database_engine.dispose()


async def test_cors_accepts_only_configured_origin(migrated_database_url: str) -> None:
    app = create_app(
        settings=runtime_settings(
            migrated_database_url,
            access_code=token_urlsafe(32),
            csrf_secret=token_urlsafe(48),
        )
    )
    try:
        client, _ = session_client(app)
        async with client:
            accepted = await client.options(
                "/api/v2/auth/session",
                headers={
                    "Origin": APP_ORIGIN,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            rejected = await client.options(
                "/api/v2/auth/session",
                headers={
                    "Origin": "https://evil.example",
                    "Access-Control-Request-Method": "POST",
                },
            )
        assert accepted.status_code == 200
        assert accepted.headers["access-control-allow-origin"] == APP_ORIGIN
        assert accepted.headers["access-control-allow-credentials"] == "true"
        assert rejected.status_code == 400
        assert "access-control-allow-origin" not in rejected.headers
    finally:
        app.state.database_engine.dispose()
